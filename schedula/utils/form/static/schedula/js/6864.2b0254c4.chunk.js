"use strict";(self.webpackChunkschedula_form=self.webpackChunkschedula_form||[]).push([[6864],{79286:function(t,e,n){n.d(e,{Z:function(){return l}});var a=n(1413),o=n(72791),c={icon:{tag:"svg",attrs:{viewBox:"64 64 896 896",focusable:"false"},children:[{tag:"defs",attrs:{},children:[{tag:"style",attrs:{}}]},{tag:"path",attrs:{d:"M482 152h60q8 0 8 8v704q0 8-8 8h-60q-8 0-8-8V160q0-8 8-8z"}},{tag:"path",attrs:{d:"M176 474h672q8 0 8 8v60q0 8-8 8H176q-8 0-8-8v-60q0-8 8-8z"}}]},name:"plus",theme:"outlined"},r=n(54291),i=function(t,e){return o.createElement(r.Z,(0,a.Z)((0,a.Z)({},t),{},{ref:e,icon:c}))};i.displayName="PlusOutlined";var l=o.forwardRef(i)},36864:function(t,e,n){n.d(e,{Z:function(){return Et}});var a=n(4942),o=n(29439),c=n(60732),r=n(75033),i=n(79286),l=n(81694),d=n.n(l),s=n(87462),u=n(1413),p=n(71002),v=n(45987),f=n(72791),b=n(33786),m=n(75179),h=n(15207),g=(0,f.createContext)(null),Z=f.forwardRef((function(t,e){var n=t.prefixCls,a=t.className,o=t.style,c=t.id,r=t.active,i=t.tabKey,l=t.children;return f.createElement("div",{id:c&&"".concat(c,"-panel-").concat(i),role:"tabpanel",tabIndex:r?0:-1,"aria-labelledby":c&&"".concat(c,"-tab-").concat(i),"aria-hidden":!r,style:o,className:d()(n,r&&"".concat(n,"-active"),a),ref:e},l)}));var k=Z,x=["key","forceRender","style","className"];function y(t){var e=t.id,n=t.activeKey,o=t.animated,c=t.tabPosition,r=t.destroyInactiveTabPane,i=f.useContext(g),l=i.prefixCls,p=i.tabs,b=o.tabPane,m="".concat(l,"-tabpane");return f.createElement("div",{className:d()("".concat(l,"-content-holder"))},f.createElement("div",{className:d()("".concat(l,"-content"),"".concat(l,"-content-").concat(c),(0,a.Z)({},"".concat(l,"-content-animated"),b))},p.map((function(t){var a=t.key,c=t.forceRender,i=t.style,l=t.className,p=(0,v.Z)(t,x),g=a===n;return f.createElement(h.default,(0,s.Z)({key:a,visible:g,forceRender:c,removeOnLeave:!!r,leavedClassName:"".concat(m,"-hidden")},o.tabPaneMotion),(function(t,n){var o=t.style,c=t.className;return f.createElement(k,(0,s.Z)({},p,{prefixCls:m,id:e,tabKey:a,animated:b,active:g,style:(0,u.Z)((0,u.Z)({},i),o),className:d()(l,c),ref:n}))}))}))))}var _=n(93433),w=n(88829),C=n(63739),S=n(75314),E=n(88834),R={width:0,height:0,left:0,top:0};function T(t,e){var n=f.useRef(t),a=f.useState({}),c=(0,o.Z)(a,2)[1];return[n.current,function(t){var a="function"===typeof t?t(n.current):t;a!==n.current&&e(a,n.current),n.current=a,c({})}]}var P=.1,N=.01,L=20,I=Math.pow(.995,L);var B=n(71605);function O(t){var e=(0,f.useState)(0),n=(0,o.Z)(e,2),a=n[0],c=n[1],r=(0,f.useRef)(0),i=(0,f.useRef)();return i.current=t,(0,B.o)((function(){var t;null===(t=i.current)||void 0===t||t.call(i)}),[a]),function(){r.current===a&&(r.current+=1,c(r.current))}}var D={width:0,height:0,left:0,top:0,right:0};function M(t){var e;return t instanceof Map?(e={},t.forEach((function(t,n){e[n]=t}))):e=t,JSON.stringify(e)}var j="TABS_DQ";function H(t){return String(t).replace(/"/g,j)}function z(t,e){var n=t.prefixCls,a=t.editable,o=t.locale,c=t.style;return a&&!1!==a.showAdd?f.createElement("button",{ref:e,type:"button",className:"".concat(n,"-nav-add"),style:c,"aria-label":(null===o||void 0===o?void 0:o.addAriaLabel)||"Add tab",onClick:function(t){a.onEdit("add",{event:t})}},a.addIcon||"+"):null}var A=f.forwardRef(z);var G=f.forwardRef((function(t,e){var n,a=t.position,o=t.prefixCls,c=t.extra;if(!c)return null;var r={};return"object"!==(0,p.Z)(c)||f.isValidElement(c)?r.right=c:r=c,"right"===a&&(n=r.right),"left"===a&&(n=r.left),n?f.createElement("div",{className:"".concat(o,"-extra-content"),ref:e},n):null})),W=n(93241),X=n(82257),K=n(11354);function q(t,e){var n=t.prefixCls,c=t.id,r=t.tabs,i=t.locale,l=t.mobile,s=t.moreIcon,u=void 0===s?"More":s,p=t.moreTransitionName,v=t.style,b=t.className,m=t.editable,h=t.tabBarGutter,g=t.rtl,Z=t.removeAriaLabel,k=t.onTabClick,x=t.getPopupContainer,y=t.popupClassName,_=(0,f.useState)(!1),w=(0,o.Z)(_,2),C=w[0],S=w[1],E=(0,f.useState)(null),R=(0,o.Z)(E,2),T=R[0],P=R[1],N="".concat(c,"-more-popup"),L="".concat(n,"-dropdown"),I=null!==T?"".concat(N,"-").concat(T):null,B=null===i||void 0===i?void 0:i.dropdownAriaLabel;var O=f.createElement(X.default,{onClick:function(t){var e=t.key,n=t.domEvent;k(e,n),S(!1)},prefixCls:"".concat(L,"-menu"),id:N,tabIndex:-1,role:"listbox","aria-activedescendant":I,selectedKeys:[T],"aria-label":void 0!==B?B:"expanded dropdown"},r.map((function(t){var e=m&&!1!==t.closable&&!t.disabled;return f.createElement(X.MenuItem,{key:t.key,id:"".concat(N,"-").concat(t.key),role:"option","aria-controls":c&&"".concat(c,"-panel-").concat(t.key),disabled:t.disabled},f.createElement("span",null,t.label),e&&f.createElement("button",{type:"button","aria-label":Z||"remove",tabIndex:0,className:"".concat(L,"-menu-item-remove"),onClick:function(e){var n,a;e.stopPropagation(),n=e,a=t.key,n.preventDefault(),n.stopPropagation(),m.onEdit("remove",{key:a,event:n})}},t.closeIcon||m.removeIcon||"\xd7"))})));function D(t){for(var e=r.filter((function(t){return!t.disabled})),n=e.findIndex((function(t){return t.key===T}))||0,a=e.length,o=0;o<a;o+=1){var c=e[n=(n+t+a)%a];if(!c.disabled)return void P(c.key)}}(0,f.useEffect)((function(){var t=document.getElementById(I);t&&t.scrollIntoView&&t.scrollIntoView(!1)}),[T]),(0,f.useEffect)((function(){C||P(null)}),[C]);var M=(0,a.Z)({},g?"marginRight":"marginLeft",h);r.length||(M.visibility="hidden",M.order=1);var j=d()((0,a.Z)({},"".concat(L,"-rtl"),g)),H=l?null:f.createElement(W.default,{prefixCls:L,overlay:O,trigger:["hover"],visible:!!r.length&&C,transitionName:p,onVisibleChange:S,overlayClassName:d()(j,y),mouseEnterDelay:.1,mouseLeaveDelay:.1,getPopupContainer:x},f.createElement("button",{type:"button",className:"".concat(n,"-nav-more"),style:M,tabIndex:-1,"aria-hidden":"true","aria-haspopup":"listbox","aria-controls":N,id:"".concat(c,"-more"),"aria-expanded":C,onKeyDown:function(t){var e=t.which;if(C)switch(e){case K.Z.UP:D(-1),t.preventDefault();break;case K.Z.DOWN:D(1),t.preventDefault();break;case K.Z.ESC:S(!1);break;case K.Z.SPACE:case K.Z.ENTER:null!==T&&k(T,t)}else[K.Z.DOWN,K.Z.SPACE,K.Z.ENTER].includes(e)&&(S(!0),t.preventDefault())}},u));return f.createElement("div",{className:d()("".concat(n,"-nav-operations"),b),style:v,ref:e},H,f.createElement(A,{prefixCls:n,locale:i,editable:m}))}var V=f.memo(f.forwardRef(q),(function(t,e){return e.tabMoving}));var Y=function(t){var e,n=t.prefixCls,o=t.id,c=t.active,r=t.tab,i=r.key,l=r.label,s=r.disabled,u=r.closeIcon,p=t.closable,v=t.renderWrapper,b=t.removeAriaLabel,m=t.editable,h=t.onClick,g=t.onFocus,Z=t.style,k="".concat(n,"-tab"),x=m&&!1!==p&&!s;function y(t){s||h(t)}var _=f.createElement("div",{key:i,"data-node-key":H(i),className:d()(k,(e={},(0,a.Z)(e,"".concat(k,"-with-remove"),x),(0,a.Z)(e,"".concat(k,"-active"),c),(0,a.Z)(e,"".concat(k,"-disabled"),s),e)),style:Z,onClick:y},f.createElement("div",{role:"tab","aria-selected":c,id:o&&"".concat(o,"-tab-").concat(i),className:"".concat(k,"-btn"),"aria-controls":o&&"".concat(o,"-panel-").concat(i),"aria-disabled":s,tabIndex:s?null:0,onClick:function(t){t.stopPropagation(),y(t)},onKeyDown:function(t){[K.Z.SPACE,K.Z.ENTER].includes(t.which)&&(t.preventDefault(),y(t))},onFocus:g},l),x&&f.createElement("button",{type:"button","aria-label":b||"remove",tabIndex:0,className:"".concat(k,"-remove"),onClick:function(t){var e;t.stopPropagation(),(e=t).preventDefault(),e.stopPropagation(),m.onEdit("remove",{key:i,event:e})}},u||m.removeIcon||"\xd7"));return v?v(_):_},F=function(t){var e=t.current||{},n=e.offsetWidth,a=void 0===n?0:n,o=e.offsetHeight;return[a,void 0===o?0:o]},Q=function(t,e){return t[e?0:1]};function J(t,e){var n,c=f.useContext(g),r=c.prefixCls,i=c.tabs,l=t.className,p=t.style,v=t.id,b=t.animated,m=t.activeKey,h=t.rtl,Z=t.extra,k=t.editable,x=t.locale,y=t.tabPosition,B=t.tabBarGutter,j=t.children,z=t.onTabClick,W=t.onTabScroll,X=(0,f.useRef)(),K=(0,f.useRef)(),q=(0,f.useRef)(),J=(0,f.useRef)(),U=(0,f.useRef)(),$=(0,f.useRef)(),tt=(0,f.useRef)(),et="top"===y||"bottom"===y,nt=T(0,(function(t,e){et&&W&&W({direction:t>e?"left":"right"})})),at=(0,o.Z)(nt,2),ot=at[0],ct=at[1],rt=T(0,(function(t,e){!et&&W&&W({direction:t>e?"top":"bottom"})})),it=(0,o.Z)(rt,2),lt=it[0],dt=it[1],st=(0,f.useState)([0,0]),ut=(0,o.Z)(st,2),pt=ut[0],vt=ut[1],ft=(0,f.useState)([0,0]),bt=(0,o.Z)(ft,2),mt=bt[0],ht=bt[1],gt=(0,f.useState)([0,0]),Zt=(0,o.Z)(gt,2),kt=Zt[0],xt=Zt[1],yt=(0,f.useState)([0,0]),_t=(0,o.Z)(yt,2),wt=_t[0],Ct=_t[1],St=function(t){var e=(0,f.useRef)([]),n=(0,f.useState)({}),a=(0,o.Z)(n,2)[1],c=(0,f.useRef)("function"===typeof t?t():t),r=O((function(){var t=c.current;e.current.forEach((function(e){t=e(t)})),e.current=[],c.current=t,a({})}));return[c.current,function(t){e.current.push(t),r()}]}(new Map),Et=(0,o.Z)(St,2),Rt=Et[0],Tt=Et[1],Pt=function(t,e,n){return(0,f.useMemo)((function(){for(var n,a=new Map,o=e.get(null===(n=t[0])||void 0===n?void 0:n.key)||R,c=o.left+o.width,r=0;r<t.length;r+=1){var i,l=t[r].key,d=e.get(l);d||(d=e.get(null===(i=t[r-1])||void 0===i?void 0:i.key)||R);var s=a.get(l)||(0,u.Z)({},d);s.right=c-s.left-s.width,a.set(l,s)}return a}),[t.map((function(t){return t.key})).join("_"),e,n])}(i,Rt,mt[0]),Nt=Q(pt,et),Lt=Q(mt,et),It=Q(kt,et),Bt=Q(wt,et),Ot=Nt<Lt+It,Dt=Ot?Nt-Bt:Nt-It,Mt="".concat(r,"-nav-operations-hidden"),jt=0,Ht=0;function zt(t){return t<jt?jt:t>Ht?Ht:t}et&&h?(jt=0,Ht=Math.max(0,Lt-Dt)):(jt=Math.min(0,Dt-Lt),Ht=0);var At=(0,f.useRef)(),Gt=(0,f.useState)(),Wt=(0,o.Z)(Gt,2),Xt=Wt[0],Kt=Wt[1];function qt(){Kt(Date.now())}function Vt(){window.clearTimeout(At.current)}!function(t,e){var n=(0,f.useState)(),a=(0,o.Z)(n,2),c=a[0],r=a[1],i=(0,f.useState)(0),l=(0,o.Z)(i,2),d=l[0],s=l[1],u=(0,f.useState)(0),p=(0,o.Z)(u,2),v=p[0],b=p[1],m=(0,f.useState)(),h=(0,o.Z)(m,2),g=h[0],Z=h[1],k=(0,f.useRef)(),x=(0,f.useRef)(),y=(0,f.useRef)(null);y.current={onTouchStart:function(t){var e=t.touches[0],n=e.screenX,a=e.screenY;r({x:n,y:a}),window.clearInterval(k.current)},onTouchMove:function(t){if(c){t.preventDefault();var n=t.touches[0],a=n.screenX,o=n.screenY;r({x:a,y:o});var i=a-c.x,l=o-c.y;e(i,l);var u=Date.now();s(u),b(u-d),Z({x:i,y:l})}},onTouchEnd:function(){if(c&&(r(null),Z(null),g)){var t=g.x/v,n=g.y/v,a=Math.abs(t),o=Math.abs(n);if(Math.max(a,o)<P)return;var i=t,l=n;k.current=window.setInterval((function(){Math.abs(i)<N&&Math.abs(l)<N?window.clearInterval(k.current):e((i*=I)*L,(l*=I)*L)}),L)}},onWheel:function(t){var n=t.deltaX,a=t.deltaY,o=0,c=Math.abs(n),r=Math.abs(a);c===r?o="x"===x.current?n:a:c>r?(o=n,x.current="x"):(o=a,x.current="y"),e(-o,-o)&&t.preventDefault()}},f.useEffect((function(){function e(t){y.current.onTouchMove(t)}function n(t){y.current.onTouchEnd(t)}return document.addEventListener("touchmove",e,{passive:!1}),document.addEventListener("touchend",n,{passive:!1}),t.current.addEventListener("touchstart",(function(t){y.current.onTouchStart(t)}),{passive:!1}),t.current.addEventListener("wheel",(function(t){y.current.onWheel(t)})),function(){document.removeEventListener("touchmove",e),document.removeEventListener("touchend",n)}}),[])}(J,(function(t,e){function n(t,e){t((function(t){return zt(t+e)}))}return!!Ot&&(et?n(ct,t):n(dt,e),Vt(),qt(),!0)})),(0,f.useEffect)((function(){return Vt(),Xt&&(At.current=window.setTimeout((function(){Kt(0)}),100)),Vt}),[Xt]);var Yt=function(t,e,n,a,o,c,r){var i,l,d,s=r.tabs,u=r.tabPosition,p=r.rtl;return["top","bottom"].includes(u)?(i="width",l=p?"right":"left",d=Math.abs(n)):(i="height",l="top",d=-n),(0,f.useMemo)((function(){if(!s.length)return[0,0];for(var n=s.length,a=n,o=0;o<n;o+=1){var c=t.get(s[o].key)||D;if(c[l]+c[i]>d+e){a=o-1;break}}for(var r=0,u=n-1;u>=0;u-=1)if((t.get(s[u].key)||D)[l]<d){r=u+1;break}return[r,a]}),[t,e,a,o,c,d,u,s.map((function(t){return t.key})).join("_"),p])}(Pt,Dt,et?ot:lt,Lt,It,Bt,(0,u.Z)((0,u.Z)({},t),{},{tabs:i})),Ft=(0,o.Z)(Yt,2),Qt=Ft[0],Jt=Ft[1],Ut=(0,C.Z)((function(){var t=arguments.length>0&&void 0!==arguments[0]?arguments[0]:m,e=Pt.get(t)||{width:0,height:0,left:0,right:0,top:0};if(et){var n=ot;h?e.right<ot?n=e.right:e.right+e.width>ot+Dt&&(n=e.right+e.width-Dt):e.left<-ot?n=-e.left:e.left+e.width>-ot+Dt&&(n=-(e.left+e.width-Dt)),dt(0),ct(zt(n))}else{var a=lt;e.top<-lt?a=-e.top:e.top+e.height>-lt+Dt&&(a=-(e.top+e.height-Dt)),ct(0),dt(zt(a))}})),$t={};"top"===y||"bottom"===y?$t[h?"marginRight":"marginLeft"]=B:$t.marginTop=B;var te=i.map((function(t,e){var n=t.key;return f.createElement(Y,{id:v,prefixCls:r,key:n,tab:t,style:0===e?void 0:$t,closable:t.closable,editable:k,active:n===m,renderWrapper:j,removeAriaLabel:null===x||void 0===x?void 0:x.removeAriaLabel,onClick:function(t){z(n,t)},onFocus:function(){Ut(n),qt(),J.current&&(h||(J.current.scrollLeft=0),J.current.scrollTop=0)}})})),ee=function(){return Tt((function(){var t=new Map;return i.forEach((function(e){var n,a=e.key,o=null===(n=U.current)||void 0===n?void 0:n.querySelector('[data-node-key="'.concat(H(a),'"]'));o&&t.set(a,{width:o.offsetWidth,height:o.offsetHeight,left:o.offsetLeft,top:o.offsetTop})})),t}))};(0,f.useEffect)((function(){ee()}),[i.map((function(t){return t.key})).join("_")]);var ne=O((function(){var t=F(X),e=F(K),n=F(q);vt([t[0]-e[0]-n[0],t[1]-e[1]-n[1]]);var a=F(tt);xt(a);var o=F($);Ct(o);var c=F(U);ht([c[0]-a[0],c[1]-a[1]]),ee()})),ae=i.slice(0,Qt),oe=i.slice(Jt+1),ce=[].concat((0,_.Z)(ae),(0,_.Z)(oe)),re=(0,f.useState)(),ie=(0,o.Z)(re,2),le=ie[0],de=ie[1],se=Pt.get(m),ue=(0,f.useRef)();function pe(){S.Z.cancel(ue.current)}(0,f.useEffect)((function(){var t={};return se&&(et?(h?t.right=se.right:t.left=se.left,t.width=se.width):(t.top=se.top,t.height=se.height)),pe(),ue.current=(0,S.Z)((function(){de(t)})),pe}),[se,et,h]),(0,f.useEffect)((function(){Ut()}),[m,jt,Ht,M(se),M(Pt),et]),(0,f.useEffect)((function(){ne()}),[h]);var ve,fe,be,me,he=!!ce.length,ge="".concat(r,"-nav-wrap");return et?h?(fe=ot>0,ve=ot!==Ht):(ve=ot<0,fe=ot!==jt):(be=lt<0,me=lt!==jt),f.createElement(w.Z,{onResize:ne},f.createElement("div",{ref:(0,E.x1)(e,X),role:"tablist",className:d()("".concat(r,"-nav"),l),style:p,onKeyDown:function(){qt()}},f.createElement(G,{ref:K,position:"left",extra:Z,prefixCls:r}),f.createElement("div",{className:d()(ge,(n={},(0,a.Z)(n,"".concat(ge,"-ping-left"),ve),(0,a.Z)(n,"".concat(ge,"-ping-right"),fe),(0,a.Z)(n,"".concat(ge,"-ping-top"),be),(0,a.Z)(n,"".concat(ge,"-ping-bottom"),me),n)),ref:J},f.createElement(w.Z,{onResize:ne},f.createElement("div",{ref:U,className:"".concat(r,"-nav-list"),style:{transform:"translate(".concat(ot,"px, ").concat(lt,"px)"),transition:Xt?"none":void 0}},te,f.createElement(A,{ref:tt,prefixCls:r,locale:x,editable:k,style:(0,u.Z)((0,u.Z)({},0===te.length?void 0:$t),{},{visibility:he?"hidden":null})}),f.createElement("div",{className:d()("".concat(r,"-ink-bar"),(0,a.Z)({},"".concat(r,"-ink-bar-animated"),b.inkBar)),style:le})))),f.createElement(V,(0,s.Z)({},t,{removeAriaLabel:null===x||void 0===x?void 0:x.removeAriaLabel,ref:$,prefixCls:r,tabs:ce,className:!he&&Mt,tabMoving:!!Xt})),f.createElement(G,{ref:q,position:"right",extra:Z,prefixCls:r})))}var U=f.forwardRef(J),$=["renderTabBar"],tt=["label","key"];function et(t){var e=t.renderTabBar,n=(0,v.Z)(t,$),a=f.useContext(g).tabs;return e?e((0,u.Z)((0,u.Z)({},n),{},{panes:a.map((function(t){var e=t.label,n=t.key,a=(0,v.Z)(t,tt);return f.createElement(k,(0,s.Z)({tab:e,key:n,tabKey:n},a))}))}),U):f.createElement(U,n)}n(60632);var nt=["id","prefixCls","className","items","direction","activeKey","defaultActiveKey","editable","animated","tabPosition","tabBarGutter","tabBarStyle","tabBarExtraContent","locale","moreIcon","moreTransitionName","destroyInactiveTabPane","renderTabBar","onChange","onTabClick","onTabScroll","getPopupContainer","popupClassName"],at=0;function ot(t,e){var n,c=t.id,r=t.prefixCls,i=void 0===r?"rc-tabs":r,l=t.className,h=t.items,Z=t.direction,k=t.activeKey,x=t.defaultActiveKey,_=t.editable,w=t.animated,C=t.tabPosition,S=void 0===C?"top":C,E=t.tabBarGutter,R=t.tabBarStyle,T=t.tabBarExtraContent,P=t.locale,N=t.moreIcon,L=t.moreTransitionName,I=t.destroyInactiveTabPane,B=t.renderTabBar,O=t.onChange,D=t.onTabClick,M=t.onTabScroll,j=t.getPopupContainer,H=t.popupClassName,z=(0,v.Z)(t,nt),A=f.useMemo((function(){return(h||[]).filter((function(t){return t&&"object"===(0,p.Z)(t)&&"key"in t}))}),[h]),G="rtl"===Z,W=function(){var t,e=arguments.length>0&&void 0!==arguments[0]?arguments[0]:{inkBar:!0,tabPane:!1};return(t=!1===e?{inkBar:!1,tabPane:!1}:!0===e?{inkBar:!0,tabPane:!1}:(0,u.Z)({inkBar:!0},"object"===(0,p.Z)(e)?e:{})).tabPaneMotion&&void 0===t.tabPane&&(t.tabPane=!0),!t.tabPaneMotion&&t.tabPane&&(t.tabPane=!1),t}(w),X=(0,f.useState)(!1),K=(0,o.Z)(X,2),q=K[0],V=K[1];(0,f.useEffect)((function(){V((0,b.Z)())}),[]);var Y=(0,m.Z)((function(){var t;return null===(t=A[0])||void 0===t?void 0:t.key}),{value:k,defaultValue:x}),F=(0,o.Z)(Y,2),Q=F[0],J=F[1],U=(0,f.useState)((function(){return A.findIndex((function(t){return t.key===Q}))})),$=(0,o.Z)(U,2),tt=$[0],ot=$[1];(0,f.useEffect)((function(){var t,e=A.findIndex((function(t){return t.key===Q}));-1===e&&(e=Math.max(0,Math.min(tt,A.length-1)),J(null===(t=A[e])||void 0===t?void 0:t.key));ot(e)}),[A.map((function(t){return t.key})).join("_"),Q,tt]);var ct=(0,m.Z)(null,{value:c}),rt=(0,o.Z)(ct,2),it=rt[0],lt=rt[1];(0,f.useEffect)((function(){c||(lt("rc-tabs-".concat(at)),at+=1)}),[]);var dt={id:it,activeKey:Q,animated:W,tabPosition:S,rtl:G,mobile:q},st=(0,u.Z)((0,u.Z)({},dt),{},{editable:_,locale:P,moreIcon:N,moreTransitionName:L,tabBarGutter:E,onTabClick:function(t,e){null===D||void 0===D||D(t,e);var n=t!==Q;J(t),n&&(null===O||void 0===O||O(t))},onTabScroll:M,extra:T,style:R,panes:null,getPopupContainer:j,popupClassName:H});return f.createElement(g.Provider,{value:{tabs:A,prefixCls:i}},f.createElement("div",(0,s.Z)({ref:e,id:c,className:d()(i,"".concat(i,"-").concat(S),(n={},(0,a.Z)(n,"".concat(i,"-mobile"),q),(0,a.Z)(n,"".concat(i,"-editable"),_),(0,a.Z)(n,"".concat(i,"-rtl"),G),n),l)},z),undefined,f.createElement(et,(0,s.Z)({},st,{renderTabBar:B})),f.createElement(y,(0,s.Z)({destroyInactiveTabPane:I},dt,{animated:W}))))}var ct=f.forwardRef(ot),rt=n(71929),it=n(1815),lt=n(29464),dt={motionAppear:!1,motionEnter:!0,motionLeave:!0};var st=n(85501),ut=function(t,e){var n={};for(var a in t)Object.prototype.hasOwnProperty.call(t,a)&&e.indexOf(a)<0&&(n[a]=t[a]);if(null!=t&&"function"===typeof Object.getOwnPropertySymbols){var o=0;for(a=Object.getOwnPropertySymbols(t);o<a.length;o++)e.indexOf(a[o])<0&&Object.prototype.propertyIsEnumerable.call(t,a[o])&&(n[a[o]]=t[a[o]])}return n};var pt=function(){return null},vt=n(55564),ft=n(89922),bt=n(67521),mt=n(25541),ht=function(t){var e=t.componentCls,n=t.motionDurationSlow;return[(0,a.Z)({},e,(0,a.Z)({},"".concat(e,"-switch"),{"&-appear, &-enter":{transition:"none","&-start":{opacity:0},"&-active":{opacity:1,transition:"opacity ".concat(n)}},"&-leave":{position:"absolute",transition:"none",inset:0,"&-start":{opacity:1},"&-active":{opacity:0,transition:"opacity ".concat(n)}}})),[(0,mt.oN)(t,"slide-up"),(0,mt.oN)(t,"slide-down")]]},gt=function(t){var e,n,o,c,r,i,l=t.componentCls,d=t.tabsCardHorizontalPadding,s=t.tabsCardHeadBackground,u=t.tabsCardGutter,p=t.colorBorderSecondary;return(0,a.Z)({},"".concat(l,"-card"),(i={},(0,a.Z)(i,"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(e={},(0,a.Z)(e,"".concat(l,"-tab"),{margin:0,padding:d,background:s,border:"".concat(t.lineWidth,"px ").concat(t.lineType," ").concat(p),transition:"all ".concat(t.motionDurationSlow," ").concat(t.motionEaseInOut)}),(0,a.Z)(e,"".concat(l,"-tab-active"),{color:t.colorPrimary,background:t.colorBgContainer}),(0,a.Z)(e,"".concat(l,"-ink-bar"),{visibility:"hidden"}),e)),(0,a.Z)(i,"&".concat(l,"-top, &").concat(l,"-bottom"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(0,a.Z)({},"".concat(l,"-tab + ").concat(l,"-tab"),{marginLeft:{_skip_check_:!0,value:"".concat(u,"px")}}))),(0,a.Z)(i,"&".concat(l,"-top"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(n={},(0,a.Z)(n,"".concat(l,"-tab"),{borderRadius:"".concat(t.borderRadiusLG,"px ").concat(t.borderRadiusLG,"px 0 0")}),(0,a.Z)(n,"".concat(l,"-tab-active"),{borderBottomColor:t.colorBgContainer}),n))),(0,a.Z)(i,"&".concat(l,"-bottom"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(o={},(0,a.Z)(o,"".concat(l,"-tab"),{borderRadius:"0 0 ".concat(t.borderRadiusLG,"px ").concat(t.borderRadiusLG,"px")}),(0,a.Z)(o,"".concat(l,"-tab-active"),{borderTopColor:t.colorBgContainer}),o))),(0,a.Z)(i,"&".concat(l,"-left, &").concat(l,"-right"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(0,a.Z)({},"".concat(l,"-tab + ").concat(l,"-tab"),{marginTop:"".concat(u,"px")}))),(0,a.Z)(i,"&".concat(l,"-left"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(c={},(0,a.Z)(c,"".concat(l,"-tab"),{borderRadius:{_skip_check_:!0,value:"".concat(t.borderRadiusLG,"px 0 0 ").concat(t.borderRadiusLG,"px")}}),(0,a.Z)(c,"".concat(l,"-tab-active"),{borderRightColor:{_skip_check_:!0,value:t.colorBgContainer}}),c))),(0,a.Z)(i,"&".concat(l,"-right"),(0,a.Z)({},"> ".concat(l,"-nav, > div > ").concat(l,"-nav"),(r={},(0,a.Z)(r,"".concat(l,"-tab"),{borderRadius:{_skip_check_:!0,value:"0 ".concat(t.borderRadiusLG,"px ").concat(t.borderRadiusLG,"px 0")}}),(0,a.Z)(r,"".concat(l,"-tab-active"),{borderLeftColor:{_skip_check_:!0,value:t.colorBgContainer}}),r))),i))},Zt=function(t){var e=t.componentCls,n=t.tabsHoverColor,o=t.dropdownEdgeChildVerticalPadding;return(0,a.Z)({},"".concat(e,"-dropdown"),Object.assign(Object.assign({},(0,bt.Wf)(t)),(0,a.Z)({position:"absolute",top:-9999,left:{_skip_check_:!0,value:-9999},zIndex:t.zIndexPopup,display:"block","&-hidden":{display:"none"}},"".concat(e,"-dropdown-menu"),{maxHeight:t.tabsDropdownHeight,margin:0,padding:"".concat(o,"px 0"),overflowX:"hidden",overflowY:"auto",textAlign:{_skip_check_:!0,value:"left"},listStyleType:"none",backgroundColor:t.colorBgContainer,backgroundClip:"padding-box",borderRadius:t.borderRadiusLG,outline:"none",boxShadow:t.boxShadowSecondary,"&-item":Object.assign(Object.assign({},bt.vS),{display:"flex",alignItems:"center",minWidth:t.tabsDropdownWidth,margin:0,padding:"".concat(t.paddingXXS,"px ").concat(t.paddingSM,"px"),color:t.colorText,fontWeight:"normal",fontSize:t.fontSize,lineHeight:t.lineHeight,cursor:"pointer",transition:"all ".concat(t.motionDurationSlow),"> span":{flex:1,whiteSpace:"nowrap"},"&-remove":{flex:"none",marginLeft:{_skip_check_:!0,value:t.marginSM},color:t.colorTextDescription,fontSize:t.fontSizeSM,background:"transparent",border:0,cursor:"pointer","&:hover":{color:n}},"&:hover":{background:t.controlItemBgHover},"&-disabled":{"&, &:hover":{color:t.colorTextDisabled,background:"transparent",cursor:"not-allowed"}}})})))},kt=function(t){var e,n,o,c,r,i,l,d,s=t.componentCls,u=t.margin,p=t.colorBorderSecondary;return d={},(0,a.Z)(d,"".concat(s,"-top, ").concat(s,"-bottom"),(0,a.Z)({flexDirection:"column"},"> ".concat(s,"-nav, > div > ").concat(s,"-nav"),(n={margin:"0 0 ".concat(u,"px 0"),"&::before":{position:"absolute",right:{_skip_check_:!0,value:0},left:{_skip_check_:!0,value:0},borderBottom:"".concat(t.lineWidth,"px ").concat(t.lineType," ").concat(p),content:"''"}},(0,a.Z)(n,"".concat(s,"-ink-bar"),{height:t.lineWidthBold,"&-animated":{transition:"width ".concat(t.motionDurationSlow,", left ").concat(t.motionDurationSlow,",\n            right ").concat(t.motionDurationSlow)}}),(0,a.Z)(n,"".concat(s,"-nav-wrap"),(e={"&::before, &::after":{top:0,bottom:0,width:t.controlHeight},"&::before":{left:{_skip_check_:!0,value:0},boxShadow:t.boxShadowTabsOverflowLeft},"&::after":{right:{_skip_check_:!0,value:0},boxShadow:t.boxShadowTabsOverflowRight}},(0,a.Z)(e,"&".concat(s,"-nav-wrap-ping-left::before"),{opacity:1}),(0,a.Z)(e,"&".concat(s,"-nav-wrap-ping-right::after"),{opacity:1}),e)),n))),(0,a.Z)(d,"".concat(s,"-top"),(0,a.Z)({},"> ".concat(s,"-nav,\n        > div > ").concat(s,"-nav"),(0,a.Z)({"&::before":{bottom:0}},"".concat(s,"-ink-bar"),{bottom:0}))),(0,a.Z)(d,"".concat(s,"-bottom"),(o={},(0,a.Z)(o,"> ".concat(s,"-nav, > div > ").concat(s,"-nav"),(0,a.Z)({order:1,marginTop:"".concat(u,"px"),marginBottom:0,"&::before":{top:0}},"".concat(s,"-ink-bar"),{top:0})),(0,a.Z)(o,"> ".concat(s,"-content-holder, > div > ").concat(s,"-content-holder"),{order:0}),o)),(0,a.Z)(d,"".concat(s,"-left, ").concat(s,"-right"),(0,a.Z)({},"> ".concat(s,"-nav, > div > ").concat(s,"-nav"),(r={flexDirection:"column",minWidth:1.25*t.controlHeight},(0,a.Z)(r,"".concat(s,"-tab"),{padding:"".concat(t.paddingXS,"px ").concat(t.paddingLG,"px"),textAlign:"center"}),(0,a.Z)(r,"".concat(s,"-tab + ").concat(s,"-tab"),{margin:"".concat(t.margin,"px 0 0 0")}),(0,a.Z)(r,"".concat(s,"-nav-wrap"),(c={flexDirection:"column","&::before, &::after":{right:{_skip_check_:!0,value:0},left:{_skip_check_:!0,value:0},height:t.controlHeight},"&::before":{top:0,boxShadow:t.boxShadowTabsOverflowTop},"&::after":{bottom:0,boxShadow:t.boxShadowTabsOverflowBottom}},(0,a.Z)(c,"&".concat(s,"-nav-wrap-ping-top::before"),{opacity:1}),(0,a.Z)(c,"&".concat(s,"-nav-wrap-ping-bottom::after"),{opacity:1}),c)),(0,a.Z)(r,"".concat(s,"-ink-bar"),{width:t.lineWidthBold,"&-animated":{transition:"height ".concat(t.motionDurationSlow,", top ").concat(t.motionDurationSlow)}}),(0,a.Z)(r,"".concat(s,"-nav-list, ").concat(s,"-nav-operations"),{flex:"1 0 auto",flexDirection:"column"}),r))),(0,a.Z)(d,"".concat(s,"-left"),(i={},(0,a.Z)(i,"> ".concat(s,"-nav, > div > ").concat(s,"-nav"),(0,a.Z)({},"".concat(s,"-ink-bar"),{right:{_skip_check_:!0,value:0}})),(0,a.Z)(i,"> ".concat(s,"-content-holder, > div > ").concat(s,"-content-holder"),(0,a.Z)({marginLeft:{_skip_check_:!0,value:"-".concat(t.lineWidth,"px")},borderLeft:{_skip_check_:!0,value:"".concat(t.lineWidth,"px ").concat(t.lineType," ").concat(t.colorBorder)}},"> ".concat(s,"-content > ").concat(s,"-tabpane"),{paddingLeft:{_skip_check_:!0,value:t.paddingLG}})),i)),(0,a.Z)(d,"".concat(s,"-right"),(l={},(0,a.Z)(l,"> ".concat(s,"-nav, > div > ").concat(s,"-nav"),(0,a.Z)({order:1},"".concat(s,"-ink-bar"),{left:{_skip_check_:!0,value:0}})),(0,a.Z)(l,"> ".concat(s,"-content-holder, > div > ").concat(s,"-content-holder"),(0,a.Z)({order:0,marginRight:{_skip_check_:!0,value:-t.lineWidth},borderRight:{_skip_check_:!0,value:"".concat(t.lineWidth,"px ").concat(t.lineType," ").concat(t.colorBorder)}},"> ".concat(s,"-content > ").concat(s,"-tabpane"),{paddingRight:{_skip_check_:!0,value:t.paddingLG}})),l)),d},xt=function(t){var e,n,o,c=t.componentCls,r=t.padding;return o={},(0,a.Z)(o,c,{"&-small":(0,a.Z)({},"> ".concat(c,"-nav"),(0,a.Z)({},"".concat(c,"-tab"),{padding:"".concat(t.paddingXS,"px 0"),fontSize:t.fontSize})),"&-large":(0,a.Z)({},"> ".concat(c,"-nav"),(0,a.Z)({},"".concat(c,"-tab"),{padding:"".concat(r,"px 0"),fontSize:t.fontSizeLG}))}),(0,a.Z)(o,"".concat(c,"-card"),(n={},(0,a.Z)(n,"&".concat(c,"-small"),(e={},(0,a.Z)(e,"> ".concat(c,"-nav"),(0,a.Z)({},"".concat(c,"-tab"),{padding:"".concat(1.5*t.paddingXXS,"px ").concat(r,"px")})),(0,a.Z)(e,"&".concat(c,"-bottom"),(0,a.Z)({},"> ".concat(c,"-nav ").concat(c,"-tab"),{borderRadius:"0 0 ".concat(t.borderRadius,"px ").concat(t.borderRadius,"px")})),(0,a.Z)(e,"&".concat(c,"-top"),(0,a.Z)({},"> ".concat(c,"-nav ").concat(c,"-tab"),{borderRadius:"".concat(t.borderRadius,"px ").concat(t.borderRadius,"px 0 0")})),(0,a.Z)(e,"&".concat(c,"-right"),(0,a.Z)({},"> ".concat(c,"-nav ").concat(c,"-tab"),{borderRadius:{_skip_check_:!0,value:"0 ".concat(t.borderRadius,"px ").concat(t.borderRadius,"px 0")}})),(0,a.Z)(e,"&".concat(c,"-left"),(0,a.Z)({},"> ".concat(c,"-nav ").concat(c,"-tab"),{borderRadius:{_skip_check_:!0,value:"".concat(t.borderRadius,"px 0 0 ").concat(t.borderRadius,"px")}})),e)),(0,a.Z)(n,"&".concat(c,"-large"),(0,a.Z)({},"> ".concat(c,"-nav"),(0,a.Z)({},"".concat(c,"-tab"),{padding:"".concat(t.paddingXS,"px ").concat(r,"px ").concat(1.5*t.paddingXXS,"px")}))),n)),o},yt=function(t){var e,n,o,c,r,i=t.componentCls,l=t.tabsHorizontalGutter,d=t.iconCls,s=t.tabsCardGutter,u="".concat(i,"-rtl");return r={},(0,a.Z)(r,u,(c={direction:"rtl"},(0,a.Z)(c,"".concat(i,"-nav"),(0,a.Z)({},"".concat(i,"-tab"),(e={margin:{_skip_check_:!0,value:"0 0 0 ".concat(l,"px")}},(0,a.Z)(e,"".concat(i,"-tab:last-of-type"),{marginLeft:{_skip_check_:!0,value:0}}),(0,a.Z)(e,d,{marginRight:{_skip_check_:!0,value:0},marginLeft:{_skip_check_:!0,value:"".concat(t.marginSM,"px")}}),(0,a.Z)(e,"".concat(i,"-tab-remove"),(0,a.Z)({marginRight:{_skip_check_:!0,value:"".concat(t.marginXS,"px")},marginLeft:{_skip_check_:!0,value:"-".concat(t.marginXXS,"px")}},d,{margin:0})),e))),(0,a.Z)(c,"&".concat(i,"-left"),(n={},(0,a.Z)(n,"> ".concat(i,"-nav"),{order:1}),(0,a.Z)(n,"> ".concat(i,"-content-holder"),{order:0}),n)),(0,a.Z)(c,"&".concat(i,"-right"),(o={},(0,a.Z)(o,"> ".concat(i,"-nav"),{order:0}),(0,a.Z)(o,"> ".concat(i,"-content-holder"),{order:1}),o)),(0,a.Z)(c,"&".concat(i,"-card").concat(i,"-top, &").concat(i,"-card").concat(i,"-bottom"),(0,a.Z)({},"> ".concat(i,"-nav, > div > ").concat(i,"-nav"),(0,a.Z)({},"".concat(i,"-tab + ").concat(i,"-tab"),{marginRight:{_skip_check_:!0,value:"".concat(s,"px")},marginLeft:{_skip_check_:!0,value:0}}))),c)),(0,a.Z)(r,"".concat(i,"-dropdown-rtl"),{direction:"rtl"}),(0,a.Z)(r,"".concat(i,"-menu-item"),(0,a.Z)({},"".concat(i,"-dropdown-rtl"),{textAlign:{_skip_check_:!0,value:"right"}})),r},_t=function(t){var e,n,o,c,r=t.componentCls,i=t.tabsCardHorizontalPadding,l=t.tabsCardHeight,d=t.tabsCardGutter,s=t.tabsHoverColor,u=t.tabsActiveColor,p=t.colorBorderSecondary;return c={},(0,a.Z)(c,r,Object.assign(Object.assign(Object.assign(Object.assign({},(0,bt.Wf)(t)),(n={display:"flex"},(0,a.Z)(n,"> ".concat(r,"-nav, > div > ").concat(r,"-nav"),(e={position:"relative",display:"flex",flex:"none",alignItems:"center"},(0,a.Z)(e,"".concat(r,"-nav-wrap"),{position:"relative",display:"flex",flex:"auto",alignSelf:"stretch",overflow:"hidden",whiteSpace:"nowrap",transform:"translate(0)","&::before, &::after":{position:"absolute",zIndex:1,opacity:0,transition:"opacity ".concat(t.motionDurationSlow),content:"''",pointerEvents:"none"}}),(0,a.Z)(e,"".concat(r,"-nav-list"),{position:"relative",display:"flex",transition:"opacity ".concat(t.motionDurationSlow)}),(0,a.Z)(e,"".concat(r,"-nav-operations"),{display:"flex",alignSelf:"stretch"}),(0,a.Z)(e,"".concat(r,"-nav-operations-hidden"),{position:"absolute",visibility:"hidden",pointerEvents:"none"}),(0,a.Z)(e,"".concat(r,"-nav-more"),{position:"relative",padding:i,background:"transparent",border:0,color:t.colorText,"&::after":{position:"absolute",right:{_skip_check_:!0,value:0},bottom:0,left:{_skip_check_:!0,value:0},height:t.controlHeightLG/8,transform:"translateY(100%)",content:"''"}}),(0,a.Z)(e,"".concat(r,"-nav-add"),Object.assign({minWidth:"".concat(l,"px"),marginLeft:{_skip_check_:!0,value:"".concat(d,"px")},padding:"0 ".concat(t.paddingXS,"px"),background:"transparent",border:"".concat(t.lineWidth,"px ").concat(t.lineType," ").concat(p),borderRadius:"".concat(t.borderRadiusLG,"px ").concat(t.borderRadiusLG,"px 0 0"),outline:"none",cursor:"pointer",color:t.colorText,transition:"all ".concat(t.motionDurationSlow," ").concat(t.motionEaseInOut),"&:hover":{color:s},"&:active, &:focus:not(:focus-visible)":{color:u}},(0,bt.Qy)(t))),e)),(0,a.Z)(n,"".concat(r,"-extra-content"),{flex:"none"}),(0,a.Z)(n,"".concat(r,"-ink-bar"),{position:"absolute",background:t.colorPrimary,pointerEvents:"none"}),n)),function(t){var e,n,o=t.componentCls,c=t.tabsActiveColor,r=t.tabsHoverColor,i=t.iconCls,l=t.tabsHorizontalGutter,d="".concat(o,"-tab");return n={},(0,a.Z)(n,d,(e={position:"relative",display:"inline-flex",alignItems:"center",padding:"".concat(t.paddingSM,"px 0"),fontSize:"".concat(t.fontSize,"px"),background:"transparent",border:0,outline:"none",cursor:"pointer","&-btn, &-remove":Object.assign({"&:focus:not(:focus-visible), &:active":{color:c}},(0,bt.Qy)(t)),"&-btn":{outline:"none",transition:"all 0.3s"},"&-remove":{flex:"none",marginRight:{_skip_check_:!0,value:-t.marginXXS},marginLeft:{_skip_check_:!0,value:t.marginXS},color:t.colorTextDescription,fontSize:t.fontSizeSM,background:"transparent",border:"none",outline:"none",cursor:"pointer",transition:"all ".concat(t.motionDurationSlow),"&:hover":{color:t.colorTextHeading}},"&:hover":{color:r}},(0,a.Z)(e,"&".concat(d,"-active ").concat(d,"-btn"),{color:t.colorPrimary,textShadow:t.tabsActiveTextShadow}),(0,a.Z)(e,"&".concat(d,"-disabled"),{color:t.colorTextDisabled,cursor:"not-allowed"}),(0,a.Z)(e,"&".concat(d,"-disabled ").concat(d,"-btn, &").concat(d,"-disabled ").concat(o,"-remove"),{"&:focus, &:active":{color:t.colorTextDisabled}}),(0,a.Z)(e,"& ".concat(d,"-remove ").concat(i),{margin:0}),(0,a.Z)(e,i,{marginRight:{_skip_check_:!0,value:t.marginSM}}),e)),(0,a.Z)(n,"".concat(d," + ").concat(d),{margin:{_skip_check_:!0,value:"0 0 0 ".concat(l,"px")}}),n}(t)),(o={},(0,a.Z)(o,"".concat(r,"-content"),{position:"relative",width:"100%"}),(0,a.Z)(o,"".concat(r,"-content-holder"),{flex:"auto",minWidth:0,minHeight:0}),(0,a.Z)(o,"".concat(r,"-tabpane"),{outline:"none","&-hidden":{display:"none"}}),o))),(0,a.Z)(c,"".concat(r,"-centered"),(0,a.Z)({},"> ".concat(r,"-nav, > div > ").concat(r,"-nav"),(0,a.Z)({},"".concat(r,"-nav-wrap"),(0,a.Z)({},"&:not([class*='".concat(r,"-nav-wrap-ping'])"),{justifyContent:"center"})))),c},wt=(0,vt.Z)("Tabs",(function(t){var e=t.controlHeightLG,n=(0,ft.TS)(t,{tabsHoverColor:t.colorPrimaryHover,tabsActiveColor:t.colorPrimaryActive,tabsCardHorizontalPadding:"".concat((e-Math.round(t.fontSize*t.lineHeight))/2-t.lineWidth,"px ").concat(t.padding,"px"),tabsCardHeight:e,tabsCardGutter:t.marginXXS/2,tabsHorizontalGutter:32,tabsCardHeadBackground:t.colorFillAlter,dropdownEdgeChildVerticalPadding:t.paddingXXS,tabsActiveTextShadow:"0 0 0.25px currentcolor",tabsDropdownHeight:200,tabsDropdownWidth:120});return[xt(n),yt(n),kt(n),Zt(n),gt(n),_t(n),ht(n)]}),(function(t){return{zIndexPopup:t.zIndexPopupBase+50}})),Ct=function(t,e){var n={};for(var a in t)Object.prototype.hasOwnProperty.call(t,a)&&e.indexOf(a)<0&&(n[a]=t[a]);if(null!=t&&"function"===typeof Object.getOwnPropertySymbols){var o=0;for(a=Object.getOwnPropertySymbols(t);o<a.length;o++)e.indexOf(a[o])<0&&Object.prototype.propertyIsEnumerable.call(t,a[o])&&(n[a[o]]=t[a[o]])}return n};function St(t){var e,n,l=t.type,s=t.className,u=t.rootClassName,p=t.size,v=t.onEdit,b=t.hideAdd,m=t.centered,h=t.addIcon,g=t.popupClassName,Z=t.children,k=t.items,x=t.animated,y=Ct(t,["type","className","rootClassName","size","onEdit","hideAdd","centered","addIcon","popupClassName","children","items","animated"]),_=y.prefixCls,w=y.moreIcon,C=void 0===w?f.createElement(r.Z,null):w,S=f.useContext(rt.E_),E=S.direction,R=S.getPrefixCls,T=S.getPopupContainer,P=R("tabs",_),N=wt(P),L=(0,o.Z)(N,2),I=L[0],B=L[1];"editable-card"===l&&(n={onEdit:function(t,e){var n=e.key,a=e.event;null===v||void 0===v||v("add"===t?a:n,t)},removeIcon:f.createElement(c.Z,null),addIcon:h||f.createElement(i.Z,null),showAdd:!0!==b});var O=R(),D=function(t,e){return t||function(t){return t.filter((function(t){return t}))}((0,st.Z)(e).map((function(t){if(f.isValidElement(t)){var e=t.key,n=t.props||{},a=n.tab,o=ut(n,["tab"]);return Object.assign(Object.assign({key:String(e)},o),{label:a})}return null})))}(k,Z),M=function(t){var e,n=arguments.length>1&&void 0!==arguments[1]?arguments[1]:{inkBar:!0,tabPane:!1};return(e=!1===n?{inkBar:!1,tabPane:!1}:!0===n?{inkBar:!0,tabPane:!0}:Object.assign({inkBar:!0},"object"===typeof n?n:{})).tabPane&&(e.tabPaneMotion=Object.assign(Object.assign({},dt),{motionName:(0,lt.mL)(t,"switch")})),e}(P,x),j=f.useContext(it.Z),H=void 0!==p?p:j;return I(f.createElement(ct,Object.assign({direction:E,getPopupContainer:T,moreTransitionName:"".concat(O,"-slide-up")},y,{items:D,className:d()((e={},(0,a.Z)(e,"".concat(P,"-").concat(H),H),(0,a.Z)(e,"".concat(P,"-card"),["card","editable-card"].includes(l)),(0,a.Z)(e,"".concat(P,"-editable-card"),"editable-card"===l),(0,a.Z)(e,"".concat(P,"-centered"),m),e),s,u,B),popupClassName:d()(g,B),editable:n,moreIcon:C,prefixCls:P,animated:M})))}St.TabPane=pt;var Et=St}}]);
//# sourceMappingURL=6864.2b0254c4.chunk.js.map