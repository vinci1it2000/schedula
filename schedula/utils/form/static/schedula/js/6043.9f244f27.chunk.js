"use strict";(self.webpackChunkschedula_form=self.webpackChunkschedula_form||[]).push([[6043],{36043:function(n,i,c){c.r(i),c.d(i,{default:function(){return l}});var t=c(1413),e=(c(72791),c(21306)),a=c(67575),o=c(60732),r=c(18050),d=c(80184);function l(n){var i=n.autofocus,c=n.disabled,l=n.formContext,s=n.id,h=n.label,g=n.onBlur,w=n.onChange,u=n.onFocus,S=n.options,p=n.readonly,m=n.value,I=l.readonlyAsDisabled,M=void 0===I||I,Z={onBlur:p?void 0:function(n){var i=n.checked;return g(s,i)},onFocus:p?void 0:function(n){var i=n.checked;return u(s,i)}};return(0,d.jsx)(e.Z,(0,t.Z)((0,t.Z)({checkedChildren:(0,d.jsx)(a.Z,{}),unCheckedChildren:(0,d.jsx)(o.Z,{}),autoFocus:i,checked:"undefined"!==typeof m&&m,disabled:c||M&&p,id:s,name:s,onChange:p?void 0:function(n){return w(n)}},Z),{},{"aria-describedby":(0,r.Jx)(s),children:S.onlyChildren?null:S.hasOwnProperty("label")?S.label:h}))}},21306:function(n,i,c){c.d(i,{Z:function(){return O}});var t=c(4942),e=c(29439),a=c(77106),o=c(81694),r=c.n(o),d=c(87462),l=c(45987),s=c(72791),h=c(75179),g=c(11354),w=["prefixCls","className","checked","defaultChecked","disabled","loadingIcon","checkedChildren","unCheckedChildren","onClick","onChange","onKeyDown"],u=s.forwardRef((function(n,i){var c,a=n.prefixCls,o=void 0===a?"rc-switch":a,u=n.className,S=n.checked,p=n.defaultChecked,m=n.disabled,I=n.loadingIcon,M=n.checkedChildren,Z=n.unCheckedChildren,b=n.onClick,f=n.onChange,x=n.onKeyDown,k=(0,l.Z)(n,w),v=(0,h.Z)(!1,{value:S,defaultValue:p}),C=(0,e.Z)(v,2),P=C[0],y=C[1];function z(n,i){var c=P;return m||(y(c=n),null===f||void 0===f||f(c,i)),c}var E=r()(o,u,(c={},(0,t.Z)(c,"".concat(o,"-checked"),P),(0,t.Z)(c,"".concat(o,"-disabled"),m),c));return s.createElement("button",(0,d.Z)({},k,{type:"button",role:"switch","aria-checked":P,disabled:m,className:E,ref:i,onKeyDown:function(n){n.which===g.Z.LEFT?z(!1,n):n.which===g.Z.RIGHT&&z(!0,n),null===x||void 0===x||x(n)},onClick:function(n){var i=z(!P,n);null===b||void 0===b||b(i,n)}}),I,s.createElement("span",{className:"".concat(o,"-inner")},s.createElement("span",{className:"".concat(o,"-inner-checked")},M),s.createElement("span",{className:"".concat(o,"-inner-unchecked")},Z)))}));u.displayName="Switch";var S=u,p=c(71929),m=c(19125),I=c(1815),M=c(90117),Z=c(69391),b=c(55564),f=c(89922),x=c(67521),k=function(n){var i,c,e,a,o,r=n.componentCls,d="".concat(r,"-inner");return(0,t.Z)({},r,(0,t.Z)({},"&".concat(r,"-small"),(o={minWidth:n.switchMinWidthSM,height:n.switchHeightSM,lineHeight:"".concat(n.switchHeightSM,"px")},(0,t.Z)(o,"".concat(r,"-inner"),(i={paddingInlineStart:n.switchInnerMarginMaxSM,paddingInlineEnd:n.switchInnerMarginMinSM},(0,t.Z)(i,"".concat(d,"-checked"),{marginInlineStart:"calc(-100% + ".concat(n.switchPinSizeSM+2*n.switchPadding,"px - ").concat(2*n.switchInnerMarginMaxSM,"px)"),marginInlineEnd:"calc(100% - ".concat(n.switchPinSizeSM+2*n.switchPadding,"px + ").concat(2*n.switchInnerMarginMaxSM,"px)")}),(0,t.Z)(i,"".concat(d,"-unchecked"),{marginTop:-n.switchHeightSM,marginInlineStart:0,marginInlineEnd:0}),i)),(0,t.Z)(o,"".concat(r,"-handle"),{width:n.switchPinSizeSM,height:n.switchPinSizeSM}),(0,t.Z)(o,"".concat(r,"-loading-icon"),{top:(n.switchPinSizeSM-n.switchLoadingIconSize)/2,fontSize:n.switchLoadingIconSize}),(0,t.Z)(o,"&".concat(r,"-checked"),(e={},(0,t.Z)(e,"".concat(r,"-inner"),(c={paddingInlineStart:n.switchInnerMarginMinSM,paddingInlineEnd:n.switchInnerMarginMaxSM},(0,t.Z)(c,"".concat(d,"-checked"),{marginInlineStart:0,marginInlineEnd:0}),(0,t.Z)(c,"".concat(d,"-unchecked"),{marginInlineStart:"calc(100% - ".concat(n.switchPinSizeSM+2*n.switchPadding,"px + ").concat(2*n.switchInnerMarginMaxSM,"px)"),marginInlineEnd:"calc(-100% + ".concat(n.switchPinSizeSM+2*n.switchPadding,"px - ").concat(2*n.switchInnerMarginMaxSM,"px)")}),c)),(0,t.Z)(e,"".concat(r,"-handle"),{insetInlineStart:"calc(100% - ".concat(n.switchPinSizeSM+n.switchPadding,"px)")}),e)),(0,t.Z)(o,"&:not(".concat(r,"-disabled):active"),(a={},(0,t.Z)(a,"&:not(".concat(r,"-checked) ").concat(d),(0,t.Z)({},"".concat(d,"-unchecked"),{marginInlineStart:n.marginXXS/2,marginInlineEnd:-n.marginXXS/2})),(0,t.Z)(a,"&".concat(r,"-checked ").concat(d),(0,t.Z)({},"".concat(d,"-checked"),{marginInlineStart:-n.marginXXS/2,marginInlineEnd:n.marginXXS/2})),a)),o)))},v=function(n){var i,c=n.componentCls;return(0,t.Z)({},c,(i={},(0,t.Z)(i,"".concat(c,"-loading-icon").concat(n.iconCls),{position:"relative",top:(n.switchPinSize-n.fontSize)/2,color:n.switchLoadingIconColor,verticalAlign:"top"}),(0,t.Z)(i,"&".concat(c,"-checked ").concat(c,"-loading-icon"),{color:n.switchColor}),i))},C=function(n){var i,c,e=n.componentCls,a="".concat(e,"-handle");return(0,t.Z)({},e,(c={},(0,t.Z)(c,a,{position:"absolute",top:n.switchPadding,insetInlineStart:n.switchPadding,width:n.switchPinSize,height:n.switchPinSize,transition:"all ".concat(n.switchDuration," ease-in-out"),"&::before":{position:"absolute",top:0,insetInlineEnd:0,bottom:0,insetInlineStart:0,backgroundColor:n.colorWhite,borderRadius:n.switchPinSize/2,boxShadow:n.switchHandleShadow,transition:"all ".concat(n.switchDuration," ease-in-out"),content:'""'}}),(0,t.Z)(c,"&".concat(e,"-checked ").concat(a),{insetInlineStart:"calc(100% - ".concat(n.switchPinSize+n.switchPadding,"px)")}),(0,t.Z)(c,"&:not(".concat(e,"-disabled):active"),(i={},(0,t.Z)(i,"".concat(a,"::before"),{insetInlineEnd:n.switchHandleActiveInset,insetInlineStart:0}),(0,t.Z)(i,"&".concat(e,"-checked ").concat(a,"::before"),{insetInlineEnd:0,insetInlineStart:n.switchHandleActiveInset}),i)),c))},P=function(n){var i,c,e,a,o=n.componentCls,r="".concat(o,"-inner");return(0,t.Z)({},o,(a={},(0,t.Z)(a,r,(i={display:"block",overflow:"hidden",borderRadius:100,height:"100%",paddingInlineStart:n.switchInnerMarginMax,paddingInlineEnd:n.switchInnerMarginMin,transition:"padding-inline-start ".concat(n.switchDuration," ease-in-out, padding-inline-end ").concat(n.switchDuration," ease-in-out")},(0,t.Z)(i,"".concat(r,"-checked, ").concat(r,"-unchecked"),{display:"block",color:n.colorTextLightSolid,fontSize:n.fontSizeSM,transition:"margin-inline-start ".concat(n.switchDuration," ease-in-out, margin-inline-end ").concat(n.switchDuration," ease-in-out"),pointerEvents:"none"}),(0,t.Z)(i,"".concat(r,"-checked"),{marginInlineStart:"calc(-100% + ".concat(n.switchPinSize+2*n.switchPadding,"px - ").concat(2*n.switchInnerMarginMax,"px)"),marginInlineEnd:"calc(100% - ".concat(n.switchPinSize+2*n.switchPadding,"px + ").concat(2*n.switchInnerMarginMax,"px)")}),(0,t.Z)(i,"".concat(r,"-unchecked"),{marginTop:-n.switchHeight,marginInlineStart:0,marginInlineEnd:0}),i)),(0,t.Z)(a,"&".concat(o,"-checked ").concat(r),(c={paddingInlineStart:n.switchInnerMarginMin,paddingInlineEnd:n.switchInnerMarginMax},(0,t.Z)(c,"".concat(r,"-checked"),{marginInlineStart:0,marginInlineEnd:0}),(0,t.Z)(c,"".concat(r,"-unchecked"),{marginInlineStart:"calc(100% - ".concat(n.switchPinSize+2*n.switchPadding,"px + ").concat(2*n.switchInnerMarginMax,"px)"),marginInlineEnd:"calc(-100% + ".concat(n.switchPinSize+2*n.switchPadding,"px - ").concat(2*n.switchInnerMarginMax,"px)")}),c)),(0,t.Z)(a,"&:not(".concat(o,"-disabled):active"),(e={},(0,t.Z)(e,"&:not(".concat(o,"-checked) ").concat(r),(0,t.Z)({},"".concat(r,"-unchecked"),{marginInlineStart:2*n.switchPadding,marginInlineEnd:2*-n.switchPadding})),(0,t.Z)(e,"&".concat(o,"-checked ").concat(r),(0,t.Z)({},"".concat(r,"-checked"),{marginInlineStart:2*-n.switchPadding,marginInlineEnd:2*n.switchPadding})),e)),a))},y=function(n){var i,c=n.componentCls;return(0,t.Z)({},c,Object.assign(Object.assign(Object.assign(Object.assign({},(0,x.Wf)(n)),(0,t.Z)({position:"relative",display:"inline-block",boxSizing:"border-box",minWidth:n.switchMinWidth,height:n.switchHeight,lineHeight:"".concat(n.switchHeight,"px"),verticalAlign:"middle",background:n.colorTextQuaternary,border:"0",borderRadius:100,cursor:"pointer",transition:"all ".concat(n.motionDurationMid),userSelect:"none"},"&:hover:not(".concat(c,"-disabled)"),{background:n.colorTextTertiary})),(0,x.Qy)(n)),(i={},(0,t.Z)(i,"&".concat(c,"-checked"),(0,t.Z)({background:n.switchColor},"&:hover:not(".concat(c,"-disabled)"),{background:n.colorPrimaryHover})),(0,t.Z)(i,"&".concat(c,"-loading, &").concat(c,"-disabled"),{cursor:"not-allowed",opacity:n.switchDisabledOpacity,"*":{boxShadow:"none",cursor:"not-allowed"}}),(0,t.Z)(i,"&".concat(c,"-rtl"),{direction:"rtl"}),i)))},z=(0,b.Z)("Switch",(function(n){var i=n.fontSize*n.lineHeight,c=n.controlHeight/2,t=i-4,e=c-4,a=(0,f.TS)(n,{switchMinWidth:2*t+8,switchHeight:i,switchDuration:n.motionDurationMid,switchColor:n.colorPrimary,switchDisabledOpacity:n.opacityLoading,switchInnerMarginMin:t/2,switchInnerMarginMax:t+2+4,switchPadding:2,switchPinSize:t,switchBg:n.colorBgContainer,switchMinWidthSM:2*e+4,switchHeightSM:c,switchInnerMarginMinSM:e/2,switchInnerMarginMaxSM:e+2+4,switchPinSizeSM:e,switchHandleShadow:"0 2px 4px 0 ".concat(new Z.C("#00230b").setAlpha(.2).toRgbString()),switchLoadingIconSize:.75*n.fontSizeIcon,switchLoadingIconColor:"rgba(0, 0, 0, ".concat(n.opacityLoading,")"),switchHandleActiveInset:"-30%"});return[y(a),P(a),C(a),v(a),k(a)]})),E=function(n,i){var c={};for(var t in n)Object.prototype.hasOwnProperty.call(n,t)&&i.indexOf(t)<0&&(c[t]=n[t]);if(null!=n&&"function"===typeof Object.getOwnPropertySymbols){var e=0;for(t=Object.getOwnPropertySymbols(n);e<t.length;e++)i.indexOf(t[e])<0&&Object.prototype.propertyIsEnumerable.call(n,t[e])&&(c[t[e]]=n[t[e]])}return c},H=s.forwardRef((function(n,i){var c,o=n.prefixCls,d=n.size,l=n.disabled,h=n.loading,g=n.className,w=n.rootClassName,u=E(n,["prefixCls","size","disabled","loading","className","rootClassName"]),Z=s.useContext(p.E_),b=Z.getPrefixCls,f=Z.direction,x=s.useContext(I.Z),k=s.useContext(m.Z),v=(null!==l&&void 0!==l?l:k)||h,C=b("switch",o),P=s.createElement("div",{className:"".concat(C,"-handle")},h&&s.createElement(a.Z,{className:"".concat(C,"-loading-icon")})),y=z(C),H=(0,e.Z)(y,2),O=H[0],D=H[1],N=r()((c={},(0,t.Z)(c,"".concat(C,"-small"),"small"===(d||x)),(0,t.Z)(c,"".concat(C,"-loading"),h),(0,t.Z)(c,"".concat(C,"-rtl"),"rtl"===f),c),g,w,D);return O(s.createElement(M.Z,null,s.createElement(S,Object.assign({},u,{prefixCls:C,className:N,disabled:v,ref:i,loadingIcon:P}))))}));H.__ANT_SWITCH=!0;var O=H}}]);
//# sourceMappingURL=6043.9f244f27.chunk.js.map