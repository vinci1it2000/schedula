"use strict";(self.webpackChunkschedula_form=self.webpackChunkschedula_form||[]).push([[8984],{73817:function(e,n){n.Z=function(e,n){var t=new Blob([JSON.stringify(e)],{type:"text/json"}),o=document.createElement("a");o.download=n,o.href=window.URL.createObjectURL(t);var l=new MouseEvent("click",{view:window,bubbles:!0,cancelable:!0});o.dispatchEvent(l),o.remove()}},338:function(e,n,t){var o=t(74165),l=t(15861);n.Z=function(e,n){if(n.preventDefault(),n.target.files.length){var t=new FileReader;t.onload=function(){var n=(0,l.Z)((0,o.Z)().mark((function n(t){var l;return(0,o.Z)().wrap((function(n){for(;;)switch(n.prev=n.next){case 0:l=t.target,e(JSON.parse(l.result));case 2:case"end":return n.stop()}}),n)})));return function(e){return n.apply(this,arguments)}}(),t.readAsText(n.target.files[0]),n.target.value=null}}},8984:function(e,n,t){t.r(n),t.d(n,{default:function(){return ae}});var o=t(1413),l=t(29439),r=t(45987),i=t(72791),a=t(20938),s=t(2458),u=t(82622),c=t(96008),d=t(14988),f=t(15787),h=t(84791),p=t(6314),m=t(65323),g=t(92365),x=t(72351),Z=t(68944),j=t(91515),v=t(23605),y=t(30142),b=t(25671),C=t(83388),S=t(49998),w=t(61431),k=t(83099),D=t(45863),B=t(36864),P=t(55076),T=t(87309),E=t(78792),M=t(91082),I=t(72131),L=t(73817),z=t(338),K=t(71861),R=t(58121),U=t.n(R),F=t(20659),A=t(14101),O=t.n(A),H=function(e,n){return n.forEach((function(n){return(0,K.applyChange)(e,null,n)})),e},N=function(e,n){return(e=e.filter((function(e,t){var o=(0,l.Z)(e,2),r=o[0];o[1];return 0===t||r<=n}))).slice(1).reduce((function(e,n){var t=(0,l.Z)(n,2),o=(t[0],t[1]);return H(e,o)}),U()(e[0][1]))},J=function(e,n){var t=O()(n,{algorithm:"sha1",encoding:"base64"}),o=function(e){var n=window.sessionStorage.getItem(e)||"",t=n.slice(28);return t=t?F.ZP.decompress.fromString(t):[],{lastHash:n.slice(0,28),changes:t}}(e),r=o.lastHash,i=o.changes;return r===t&&(i=i.slice(0,i.length-1)),{changes:i,diffList:i.map((function(e){var n=(0,l.Z)(e,3),o=n[0],r=(n[1],n[2]);return{date:o,sameAsCurrent:t===r}})).reverse()}},V=t(3111),W=t(85152),$=t(79745),_=t(37481),Y=t(66364),q=t.n(Y),G=t(80184),Q=["children","render","savingData","savingKey","items","defaultSelectedKeys","urlContact","userProps","cloudUrl","hideRun","hideDebug","hideSideMenu","footer","theme","contentProps"],X=i.lazy((function(){return Promise.all([t.e(2320),t.e(9003)]).then(t.bind(t,59817))})),ee=i.lazy((function(){return Promise.all([t.e(1583),t.e(7828),t.e(4596)]).then(t.bind(t,74596))})),ne=i.lazy((function(){return Promise.all([t.e(1583),t.e(4569)]).then(t.bind(t,84569))})),te=i.lazy((function(){return Promise.all([t.e(7828),t.e(1177)]).then(t.bind(t,11177))})),oe=b.Z.Header,le=b.Z.Content,re=b.Z.Footer,ie=b.Z.Sider,ae=function(e){var n=e.children,t=e.render,R=e.savingData,A=void 0===R||R,Y=e.savingKey,ae=e.items,se=void 0===ae?[]:ae,ue=e.defaultSelectedKeys,ce=void 0===ue?["0"]:ue,de=e.urlContact,fe=e.userProps,he=e.cloudUrl,pe=e.hideRun,me=void 0!==pe&&pe,ge=e.hideDebug,xe=void 0!==ge&&ge,Ze=e.hideSideMenu,je=void 0!==Ze&&Ze,ve=e.footer,ye=void 0===ve?null:ve,be=e.theme,Ce=void 0===be?"dark":be,Se=e.contentProps,we=(0,r.Z)(e,Q),ke=(0,(0,_.useLocaleStore)().getLocale)("App"),De=(0,i.useRef)(null),Be=t.formContext,Pe=Be.form,Te=Pe.state.userInfo,Ee=void 0===Te?{}:Te,Me=!q()(Ee),Ie=(0,I.Z)(Pe.formElement),Le=(0,l.Z)(Ie,2),ze=Le[0],Ke=Le[1],Re=Ke.isEnabled,Ue=Ke.toggleFullscreen,Fe=Y||(t?"schedula-"+Pe.props.$id+"-"+t.idSchema.$id+"-formData":"form"),Ae=(0,i.useState)(A),Oe=(0,l.Z)(Ae,2),He=Oe[0],Ne=Oe[1],Je=t.formData,Ve=(0,i.useState)(!1),We=(0,l.Z)(Ve,2),$e=We[0],_e=We[1],Ye=(0,i.useState)(null),qe=(0,l.Z)(Ye,2),Ge=qe[0],Qe=qe[1];(0,i.useEffect)((function(){if(He)try{!function(e,n){var t=O()(n,{algorithm:"sha1",encoding:"base64"}),o=window.sessionStorage.getItem(e)||"";if(o.slice(0,28)!==t){var r,i=o.slice(28);i=i?F.ZP.decompress.fromString(i):[];var a=Math.floor(Date.now()/6e4);if((i=i.filter((function(e,n){var t=(0,l.Z)(e,2),o=t[0];return t[1],o<a}))).length){if(!(r=(0,K.diff)(i.slice(1).reduce((function(e,n){var t=(0,l.Z)(n,2),o=(t[0],t[1]);return H(e,o)}),U()(i[0][1])),n)))return}else r=n;i.push([a,r,t]),window.sessionStorage.setItem(e,"".concat(t).concat(F.ZP.compress.toString(i)))}}(Fe,Je)}catch(e){Ne(!1),Pe.props.notify({message:ke.autoSavingErrorTitle,description:e.message,type:"warning"})}}),[Fe,Je,He,ke.autoSavingErrorTitle]);var Xe=(0,i.useMemo)((function(){return $e?J(Fe,Je):{}}),[Fe,Je,$e]),en=Xe.changes,nn=Xe.diffList,tn=(0,i.useMemo)((function(){return null!==Ge&&en?N(en,Ge):null}),[en,Ge]),on=se.map((function e(n){return n.href&&"string"===typeof n.label&&(n.label=(0,G.jsx)("a",{href:n.href,children:n.label})),n.children&&(n.children=n.children.map(e)),n})),ln=(0,i.useState)(ce[0]),rn=(0,l.Z)(ln,2),an=rn[0],sn=rn[1],un=(0,i.useState)(!1),cn=(0,l.Z)(un,2),dn=cn[0],fn=cn[1],hn=(0,i.useState)(!1),pn=(0,l.Z)(hn,2),mn=pn[0],gn=pn[1],xn=(0,i.useState)(null),Zn=(0,l.Z)(xn,2),jn=Zn[0],vn=Zn[1];return(0,i.useEffect)((function(){!Me&&jn&&vn(null)}),[Me,jn]),"number"===typeof ye&&(ye=n[ye]),(0,G.jsxs)(b.Z,(0,o.Z)((0,o.Z)({style:{height:"100%"}},we),{},{children:[je?null:(0,G.jsxs)(ie,{collapsible:!0,defaultCollapsed:!0,style:{overflowY:"auto",marginBottom:"48px"},theme:Ce,children:[(0,G.jsx)("div",{style:{height:32,margin:16,background:"rgba(255, 255, 255, 0.2)"}}),(0,G.jsx)("input",{ref:De,accept:["json"],type:"file",hidden:!0,onChange:function(e){(0,z.Z)(t.parent.props.onChange,e)}}),(0,G.jsx)(C.Z,{mode:"inline",theme:Ce,selectable:!1,onClick:function(e){var n=e.key;"run"===n?Pe.submit():"debug"===n?Pe.onSubmit(null,{headers:{Debug:"true"}}):"clean"===n?S.Z.confirm({title:ke.cleanConfirm,onOk:function(){t.parent.props.onChange({})},onCancel:function(){}}):"fullscreen"===n?Ue():"download"===n?(0,L.Z)(t.formData,"file.json"):"upload"===n?De.current.click():"autosave"===n?Ne(!He):"restore"===n?_e(!$e):"cloud-download"===n?fn(!0):"cloud-upload"===n&&gn(!0)},items:[me?null:{icon:(0,G.jsx)(a.Z,{}),key:"run",label:ke.runButton},xe?null:{icon:(0,G.jsx)(s.Z,{}),key:"debug",label:ke.debugButton},{icon:(0,G.jsx)(u.Z,{}),key:"clean",label:ke.cleanButton},Re?{icon:ze?(0,G.jsx)(c.Z,{}):(0,G.jsx)(d.Z,{}),key:"fullscreen",label:(0,G.jsx)(w.Z,{title:ze?ke.disableFullscreen:ke.enableFullscreen,placement:"right",children:ke.fullscreenButton})}:null,Me&&he?{icon:(0,G.jsx)(f.Z,{}),key:"cloud",label:ke.cloudButton,children:[{icon:(0,G.jsx)(h.Z,{}),key:"cloud-download",label:(0,G.jsx)(w.Z,{title:ke.cloudDownloadTooltip,placement:"right",children:ke.cloudDownloadButton})},{icon:(0,G.jsx)(p.Z,{}),key:"cloud-upload",label:(0,G.jsx)(w.Z,{title:ke.cloudUploadTooltip,placement:"right",children:ke.cloudUploadButton})}]}:null,{icon:(0,G.jsx)(m.Z,{}),key:"files",label:ke.filesButton,children:[{icon:(0,G.jsx)(g.Z,{}),key:"download",label:(0,G.jsx)(w.Z,{title:ke.downloadTooltip,placement:"right",children:ke.downloadButton})},{icon:(0,G.jsx)(x.Z,{}),key:"upload",label:(0,G.jsx)(w.Z,{title:ke.uploadTooltip,placement:"right",children:ke.uploadButton})},{icon:He?(0,G.jsx)(Z.Z,{}):(0,G.jsx)(j.Z,{}),key:"autosave",label:(0,G.jsx)(w.Z,{title:He?ke.autoSavingTooltip:ke.autoSaveTooltip,placement:"right",children:He?ke.autoSavingButton:ke.autoSaveButton})},{icon:(0,G.jsx)(v.Z,{}),key:"restore",label:(0,G.jsx)(w.Z,{title:ke.restoreTooltip,placement:"right",children:ke.restoreButton})}]}].filter((function(e){return null!==e}))})]}),(0,G.jsxs)(b.Z,{children:[(0,G.jsx)(oe,{style:{position:"sticky",top:0,zIndex:1,width:"100%",padding:0},children:(0,G.jsxs)("div",{style:{display:"flex"},children:[on.length?(0,G.jsx)(C.Z,(0,o.Z)({theme:Ce,mode:"horizontal",style:{flex:"auto",minWidth:0},defaultSelectedKeys:ce,items:on,onSelect:function(e){var n=e.key;sn(n)}},we),"left-menu"):(0,G.jsx)("div",{style:{flex:"auto",minWidth:0}}),(0,G.jsxs)(k.Z,{className:"ant-menu-".concat(Ce," css-dev-only-do-not-override-j0nf2s"),style:{paddingLeft:"16px",paddingRight:"16px",cursor:"pointer"},children:[jn?(0,G.jsxs)(D.Z.Text,{keyboard:!0,children:["# ",jn.id," - ",jn.name]}):null,(0,G.jsx)(te,{form:Pe,formContext:Be,urlContact:de}),(0,G.jsx)(ne,{form:Pe}),fe?(0,G.jsx)(ee,(0,o.Z)({form:Pe},fe)):null]},"right-element")]})}),(0,G.jsxs)(le,(0,o.Z)((0,o.Z)({style:{margin:"16px 16px"}},Se),{},{children:[on.length?(0,G.jsx)(B.Z,{activeKey:String(an),items:n.map((function(e,n){return{key:String(n),children:e,style:{height:"100%"}}})),renderTabBar:function(){return null},style:{height:"100%"}}):n,(0,G.jsx)(P.Z.BackTop,{}),he?(0,G.jsxs)(G.Fragment,{children:[(0,G.jsx)(V.Z,{uiSchema:{"ui:cloudUrl":he,"ui:modal":{open:dn,onCancel:function(){fn(!1)}},"ui:currentKey":jn,"ui:onSelect":function(e){fn(!1),vn(e)}},formData:Pe.state.formData,onChange:Pe.onChange,formContext:t.formContext}),(0,G.jsx)(W.Z,{uiSchema:{"ui:cloudUrl":he,"ui:currentKey":jn,"ui:onSave":function(e){gn(!1),vn(e)},"ui:modal":{open:mn,onCancel:function(){gn(!1)}}},formData:Pe.state.formData,onChange:Pe.onChange,formContext:t.formContext})]}):null,(0,G.jsx)($.My,{title:ke.restoreModalTitle,open:$e,onOk:function(){_e(!1)},onCancel:function(){_e(!1)},footer:[(0,G.jsx)(T.ZP,{onClick:function(){_e(!1),function(e){window.sessionStorage.removeItem(e)}(Fe)},children:ke.restoreEraseButton},"erase"),(0,G.jsx)(T.ZP,{onClick:function(){_e(!1)},children:ke.restoreCloseButton},"close")],children:(0,G.jsx)(E.ZP,{size:"small",dataSource:nn,renderItem:function(e){return(0,G.jsxs)(E.ZP.Item,{children:[(0,G.jsx)(E.ZP.Item.Meta,{avatar:(0,G.jsx)(M.Z,{title:ke.restoreConfirm,placement:"top",onConfirm:function(n){n&&n.preventDefault(),t.parent.props.onChange(N(en,e.date)),_e(!1)},children:(0,G.jsx)(T.ZP,{type:"primary",shape:"circle",icon:(0,G.jsx)(v.Z,{})})}),title:new Date(6e4*e.date).toLocaleString()}),e.sameAsCurrent?null:(0,G.jsx)(w.Z,{title:ke.restoreDifferences,placement:"bottom",children:(0,G.jsx)(T.ZP,{type:"primary",shape:"circle",icon:(0,G.jsx)(y.Z,{}),onClick:function(){Qe(e.date)}})})]})}})}),(0,G.jsx)($.My,{title:ke.restoreTitleDifferences,open:null!==Ge,onCancel:function(){Qe(null)},footer:[(0,G.jsx)(T.ZP,{onClick:function(){_e(!1),t.parent.props.onChange(tn),Qe(null)},children:ke.restoreRestoreButton},"restore"),(0,G.jsx)(T.ZP,{onClick:function(){Qe(null)},children:ke.restoreCloseButton},"close")],children:Ge?(0,G.jsx)(X,{rightTitle:new Date(6e4*Math.floor(Date.now()/6e4)).toLocaleString()+" (".concat(ke.restoreCurrent,")"),leftTitle:new Date(6e4*Ge).toLocaleString(),oldValue:tn,newValue:Je}):null})]})),ye?(0,G.jsx)(re,{style:{position:"sticky",bottom:0,zIndex:1,width:"100%",padding:"16px 50px",textAlign:"center"},children:ye}):null]})]}))}}}]);
//# sourceMappingURL=8984.8a3217bd.chunk.js.map