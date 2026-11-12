"""Observe requests and attempted network APIs across the full browser context."""
from urllib.parse import urldefrag


INIT = r"""(() => {
  const local = u => /^(data:|blob:|#)/i.test(String(u));
  const report = (api, u) => {
    if (!local(u)) window.__skillNetworkAttempt({api, url:String(u)}).catch(()=>{});
  };
  const wrap = (obj, key, before) => {
    const native = obj?.[key]; if(typeof native !== 'function') return;
    obj[key] = function(...args){ before(...args); return Reflect.apply(native, this, args); };
  };
  wrap(window, 'fetch', u => report('fetch', u?.url ?? u));
  wrap(navigator, 'sendBeacon', u => report('sendBeacon', u));
  const urls = new WeakMap();
  const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest){ urls.set(this,url); return open.call(this,method,url,...rest); };
  XMLHttpRequest.prototype.send = function(...args){ report('XMLHttpRequest',urls.get(this)); return send.apply(this,args); };
  for(const name of ['WebSocket','EventSource','Worker','SharedWorker','WebTransport']) {
    const native=window[name]; if(typeof native !== 'function') continue;
    window[name]=new Proxy(native,{construct(target,args,newTarget){report(name,args[0]);return Reflect.construct(target,args,newTarget);}});
  }
  if(navigator.serviceWorker) wrap(navigator.serviceWorker,'register',u=>report('serviceWorker.register',u));
  const rtc=window.RTCPeerConnection;
  if(rtc) window.RTCPeerConnection=new Proxy(rtc,{construct(target,args,newTarget){
    report('RTCPeerConnection','webrtc:connection');return Reflect.construct(target,args,newTarget);
  }});
  addEventListener('securitypolicyviolation',e=>{
    if(e.blockedURI && !['inline','eval'].includes(e.blockedURI)) report('CSP:'+e.violatedDirective,e.blockedURI);
  });
  const hints = new Set(['preconnect','dns-prefetch','prefetch','modulepreload','preload']);
  const inspect = node => {
    if(node?.nodeType !== 1) return;
    for(const link of [node, ...node.querySelectorAll('link')]) {
      if(link.tagName === 'LINK' && [...link.relList].some(rel=>hints.has(rel)))
        report('resource-hint',link.href);
    }
  };
  new MutationObserver(records=>{
    for(const r of records){ if(r.type === 'attributes') inspect(r.target); else r.addedNodes.forEach(inspect); }
  }).observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['href','rel']});
})();"""


class NetworkAudit:
    def __init__(self, context, page, entry_url):
        self.context, self.page = context, page
        self.entry_url = urldefrag(entry_url)[0]
        self.requests, self.blocked, self.sockets, self.api_attempts = [], [], [], []
        self.cdp_extra = []
        self.document_count = 0
        self.socket_supported = hasattr(context, 'route_web_socket')
        self.cdp_supported = False
        context.expose_binding('__skillNetworkAttempt', lambda source, event: self.api_attempts.append(event))
        context.add_init_script(INIT)
        context.on('request', self._request)
        context.route('**/*', self._route)
        if self.socket_supported:
            def block_socket(socket):
                self.sockets.append(socket.url)
                # A routed socket is mocked and never contacts the server unless
                # connect_to_server() is called. Do not close synchronously here:
                # Chromium/Playwright can deadlock while constructing the socket.
                # Context teardown disposes it; the attempted socket fails QA.
            context.route_web_socket('**/*', block_socket)
        try:
            self.cdp = context.new_cdp_session(page)
            self.cdp.send('Network.enable')
            self.cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
            self.cdp.on('Network.requestWillBeSent', self._cdp_request)
            self.cdp_supported = True
        except Exception:
            pass

    @staticmethod
    def local(url):
        return url.lower().startswith(('data:', 'blob:'))

    def _request(self, request):
        self.requests.append({'url': request.url, 'type': request.resource_type})

    def _cdp_request(self, event):
        url = event['request']['url']
        # Main-document authorization is stricter in the route callback. CDP also
        # sees requests such as the implicit favicon that routing may omit.
        if not self.local(url) and urldefrag(url)[0] != self.entry_url:
            self.cdp_extra.append({'url': url, 'type': event.get('type')})

    def _route(self, route):
        request = route.request
        url = request.url
        try:
            main = request.frame == self.page.main_frame
        except Exception:
            main = False  # Worker requests have no frame.
        initial = (self.document_count == 0 and main and request.is_navigation_request()
                   and request.resource_type == 'document' and urldefrag(url)[0] == self.entry_url)
        if initial:
            self.document_count += 1
            route.continue_()
        elif self.local(url):
            route.continue_()
        else:
            self.blocked.append({'url': url, 'type': request.resource_type})
            route.abort()

    def result(self):
        evidence = {'entryDocuments': self.document_count, 'requests': self.requests,
                    'blockedRequests': self.blocked, 'websockets': self.sockets,
                    'apiAttempts': self.api_attempts, 'cdpExtraRequests': self.cdp_extra,
                    'cacheDisabled': self.cdp_supported, 'serviceWorkers': 'blocked',
                    'webSocketRouting': self.socket_supported,
                    'scope': 'isolated HTML and exercised interactions; excludes unrelated browser/hosting sign-in traffic'}
        bad = self.blocked or self.sockets or self.api_attempts or self.cdp_extra
        status = 'failed' if bad or self.document_count > 1 else 'passed' if (
            self.document_count == 1 and self.socket_supported and self.cdp_supported) else 'unverified'
        return {'status': status, 'evidence': evidence}
