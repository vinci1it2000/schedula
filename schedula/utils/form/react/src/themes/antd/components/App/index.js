import React, {useEffect, useRef, useState, useMemo, Suspense} from 'react';
import {useLocation, Link} from 'react-router-dom';
import {
    UploadOutlined,
    CaretRightOutlined,
    BugOutlined,
    LaptopOutlined,
    CompressOutlined,
    DownloadOutlined,
    ExpandOutlined,
    DeleteOutlined,
    CloudUploadOutlined,
    CloudDownloadOutlined,
    CloudOutlined,
    WarningOutlined,
    ExportOutlined
} from '@ant-design/icons';
import {
    Layout,
    Menu,
    Flex,
    FloatButton,
    Tooltip,
    Modal,
    Drawer,
    Typography,
    Result,
    Skeleton,
    theme
} from 'antd';
import {useFullscreen} from "ahooks";
import exportJSON from "../../../../core/utils/Export"
import uploadJSON from "../../../../core/utils/Import"
import CloudDownloadField from '../../fields/CloudDownloadField'
import CloudUploadField from '../../fields/CloudUploadField'
import {useLocaleStore} from "../../models/locale";
import isEmpty from "lodash/isEmpty";
import {createLayoutElement} from "../../../../core";
import {saveAs} from 'file-saver';

const Errors = React.lazy(() => import('../Errors/Drawer'))
const Debug = React.lazy(() => import('../Debug'))
const Cookies = React.lazy(() => import('../Cookies'))
const UserNav = React.lazy(() => import('./User'))
const LanguageNav = React.lazy(() => import('./Language'))
const ContactNav = React.lazy(() => import('./Contact'))
const ContentPage = React.lazy(() => import('./ContentPages'))
const {useToken} = theme;
const formatItem = ({path, label, children,href, ...item}, index) => {
    if (path && typeof label === 'string') {
        label = <Link to={path}>{label}</Link>
    } else if (href && typeof label === 'string') {
        label = <a href={href} rel="noopener noreferrer">
            {label}
        </a>
    }
    if (children) {
        children = children.map((d, i) => {
            return formatItem(d, `${index}-${i}`)
        })
    }
    return {path, label, children, key: `tmp-${index}`, ...item}
}

function* formatPaths({path, key, children = []}) {
    if (path) {
        yield {path, key}
    }
    for (const item of children) {
        yield* formatPaths(item);
    }
}

function* formatRoutes({path, key, children = [], ...props}, elements) {
    if (path && typeof key === 'number') {
        yield {path, element: elements[key], key, ...props}
    }
    for (const item of children) {
        yield* formatRoutes(item, elements);
    }
}

const {Header, Content, Footer, Sider} = Layout;
const App = (
    {
        children,
        render,
        items = [],
        urlContact,
        languages = true,
        logo,
        userProps,
        cloudUrl,
        urlConsent,
        hideErrors = false,
        hideExport = true,
        hideNav = false,
        hideRun = false,
        hideDebug = false,
        hideClean = false,
        hideFullscreen = false,
        hideFiles = false,
        hideSideMenu = false,
        page403 = null,
        footer = null,
        theme = 'light',
        contentProps,
        homePath = '/',
        ...props
    }
) => {
    const {token} = useToken();
    const {getLocale} = useLocaleStore()
    const locale = getLocale('App')
    const impButton = useRef(null);
    const mainLayout = useRef(null);
    const {formContext} = render
    const {form} = formContext
    const {userInfo = {}} = form.state
    const logged = !isEmpty(userInfo)
    const [isFullscreen, {
        isEnabled: isFullscreenEnabled,
        toggleFullscreen
    }] = useFullscreen(form.formElement);
    const _items = useMemo(() => (items.map(formatItem)), [])
    const {pathname} = useLocation()
    const {routes} = useMemo(() => {
        const routes = [...formatRoutes({children: items}, children)]
        return {routes}
    }, [children, items])

    const [selectedKeys, setSelectedKeys] = useState(null);
    useEffect(() => {
        const _routes = [...formatPaths({children: _items})].sort((a, b) => (b.path || "").length - (a.path || "").length)
        let {
            key = null
        } = _routes.find(({path}) => pathname.startsWith(path)) || {}
        setSelectedKeys(key === null ? null : [String(key)])
    }, [_items])
    const [visitedRoutes, setVisitedRoutes] = useState({});
    useEffect(() => {
        setVisitedRoutes((visited) => ({...visited, [pathname]: true}))
    }, [pathname])

    const [openCloudDownload, setOpenCloudDownload] = useState(false);
    const [openCloudUpload, setOpenCloudUpload] = useState(false);
    const [currentDataId, setCurrentDataId] = useState(null);
    useEffect(() => {
        if (!logged && currentDataId) {
            setCurrentDataId(null)
        }
    }, [logged, currentDataId])

    if (typeof footer === 'number')
        footer = children[footer]
    const {errors, debugUrl} = form.state
    const [openErrors, setOpenErrors] = useState(false);
    const [openDebug, setOpenDebug] = useState(!!debugUrl);
    useEffect(() => {
        if (!!debugUrl) {
            setOpenDebug(true)
        }
    }, [debugUrl]);
    const [sliderCollapsed, setSliderCollapsed] = useState(true);

    const mustLogin = useMemo(() => {
        const {loginRequired = false} = userProps || {}
        return loginRequired === true || (typeof loginRequired === 'object' && loginRequired[pathname])
    }, [pathname, userProps])

    const logoElement = useMemo(() => {
        return logo ? createLayoutElement({
            key: 'logo', layout: logo, render, isArray: false
        }) : null
    }, [logo, render])

    return <Layout key={'main'} style={{height: '100%'}}>
        {!hideNav || currentDataId || urlContact || languages || userProps || _items.length || logo ?
            <Header
                key={'bar'}
                className={`ant-menu-${theme}`}
                style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 1,
                    width: '100%',
                    padding: 0,
                    display: "flex",
                    borderBottomWidth: 1,
                    borderBottomColor: token.colorBorder,
                    borderBottomStyle: 'solid',
                }}>
                <div key={'logo'} style={{
                    height: "100%",
                    textAlign: 'center',
                    lineHeight: 'normal'
                }}>{logoElement}</div>
                {_items.length ? <Menu
                    key={'left-menu'}
                    theme={theme}
                    mode="horizontal"
                    style={{flex: "auto", minWidth: 0, border: 0}}
                    selectedKeys={selectedKeys}
                    items={_items}
                    onSelect={({key}) => {
                        setSelectedKeys([key])
                    }}
                    {...props}
                /> : <div key={'left-menu-place'}
                          style={{flex: "auto", minWidth: 0}}/>}
                {currentDataId || urlContact || languages || userProps ?
                    <Flex key={'right-element'}
                          style={{
                              paddingLeft: '16px',
                              paddingRight: '16px',
                              cursor: 'pointer'
                          }}
                          gap="middle">
                        {currentDataId ? <Typography.Text keyboard>
                            # {currentDataId.id} - {currentDataId.name}
                        </Typography.Text> : null}
                        {urlContact ? <Suspense><ContactNav
                            key={'contact'}
                            render={render}
                            containerRef={mainLayout}
                            urlContact={urlContact}/></Suspense> : null}
                        <Suspense><LanguageNav
                            key={'language'}
                            render={render}
                            languages={languages}/></Suspense>
                        {userProps ?
                            <Suspense><UserNav
                                key={'user'}
                                render={render}
                                containerRef={mainLayout}
                                {...userProps}/></Suspense> : null}
                    </Flex> : null}
            </Header> : null}
        <Layout hasSider key={"main"} ref={mainLayout} style={{
            position: 'relative'
        }}>
            {hideSideMenu || (hideRun && hideDebug && hideClean && hideFullscreen && !cloudUrl && hideFiles) ? null :
                <Sider key={"side-left"} collapsible
                       onCollapse={(collapsed) => {
                           setSliderCollapsed(collapsed)
                       }} defaultCollapsed={true} style={{
                    overflowY: "auto",
                    marginBottom: "44px"
                }} theme={theme}>
                    <input
                        ref={impButton} accept={['json']}
                        type={'file'}
                        hidden onChange={(event) => {
                        uploadJSON(render.parent.props.onChange, event)
                    }}/>
                    <Menu
                        key={'menu'}
                        mode="inline"
                        theme={theme}
                        selectable={false}
                        onClick={({key}) => {
                            if (key === 'run') {
                                form.onSubmit(null, {})
                            } else if (key === 'debug') {
                                form.onSubmit(null, {headers: {'Debug': 'true'}})
                            } else if (key === 'clean') {
                                Modal.confirm({
                                    title: locale.cleanConfirm,
                                    onOk() {
                                        render.parent.props.onChange({})
                                    },
                                    onCancel() {
                                    }
                                });
                            } else if (key === 'fullscreen') {
                                toggleFullscreen()
                            } else if (key === 'download') {
                                exportJSON(render.formData, 'file.json')
                            } else if (key === 'export') {
                                form.setState({
                                    ...form.state, loading: true
                                }, () => {
                                    setTimeout(() => {
                                        form.postData({
                                            rawResponse: true,
                                            url: `/export-form/${form.props.name}`,
                                            data: form.state.formData
                                        }, async ({data: response}) => {
                                            saveAs(await response.blob(), `${form.props.name}.zip`);
                                            form.setState({
                                                ...form.state,
                                                loading: false
                                            })
                                        }, () => {
                                            form.setState({
                                                ...form.state,
                                                loading: false
                                            })
                                        })
                                    }, 1000);
                                })
                            } else if (key === 'upload') {
                                impButton.current.click()
                            } else if (key === 'cloud-download') {
                                setOpenCloudDownload(true)
                            } else if (key === 'cloud-upload') {
                                setOpenCloudUpload(true)
                            }
                        }}
                        items={[hideRun ? null : {
                            icon: <CaretRightOutlined/>,
                            key: form.state.runnable ? 'run' : 'no-run',
                            className: 'run-button',
                            disabled: !form.state.runnable,
                            label: locale.runButton
                        }, hideDebug ? null : {
                            icon: <BugOutlined/>,
                            key: form.state.debuggable ? 'debug' : 'no-debug',
                            className: 'debug-button',
                            disabled: !form.state.debuggable,
                            label: locale.debugButton
                        }, hideClean ? null : {
                            icon: <DeleteOutlined/>,
                            key: 'clean',
                            className: 'clean-button',
                            label: locale.cleanButton
                        }, !hideFullscreen && isFullscreenEnabled ? {
                            icon: isFullscreen ? <CompressOutlined/> :
                                <ExpandOutlined/>,
                            className: 'fullscreen-button',
                            key: 'fullscreen',
                            label: <Tooltip
                                title={isFullscreen ? locale.disableFullscreen : locale.enableFullscreen}
                                placement="right">
                                {locale.fullscreenButton}
                            </Tooltip>
                        } : null, logged && cloudUrl ? {
                            icon: <CloudOutlined/>,
                            key: 'cloud',
                            className: 'cloud-button',
                            label: locale.cloudButton,
                            children: [
                                {
                                    icon: <CloudDownloadOutlined/>,
                                    key: 'cloud-download',
                                    className: 'cloud-download-button',
                                    label: <Tooltip
                                        title={locale.cloudDownloadTooltip}
                                        placement="right">
                                        {locale.cloudDownloadButton}
                                    </Tooltip>
                                },
                                {
                                    icon: <CloudUploadOutlined/>,
                                    key: 'cloud-upload',
                                    className: 'cloud-upload-button',
                                    label: <Tooltip
                                        title={locale.cloudUploadTooltip}
                                        placement="right">
                                        {locale.cloudUploadButton}
                                    </Tooltip>
                                }
                            ]
                        } : null, hideFiles ? null : {
                            icon: <LaptopOutlined/>,
                            key: 'files',
                            className: 'files-button',
                            label: locale.filesButton,
                            children: [
                                {
                                    icon: <DownloadOutlined/>,
                                    key: 'download',
                                    className: 'download-button',
                                    label: <Tooltip
                                        title={locale.downloadTooltip}
                                        placement="right">
                                        {locale.downloadButton}
                                    </Tooltip>
                                },
                                {
                                    icon: <UploadOutlined/>,
                                    key: 'upload',
                                    className: 'upload-button',
                                    label: <Tooltip
                                        title={locale.uploadTooltip}
                                        placement="right">
                                        {locale.uploadButton}
                                    </Tooltip>
                                },
                                hideExport ? null : {
                                    icon: <ExportOutlined/>,
                                    key: 'export',
                                    className: 'export-button',
                                    label: <Tooltip
                                        title={locale.exportTooltip}
                                        placement="right">
                                        {locale.exportButton}
                                    </Tooltip>
                                }
                            ].filter(v => v !== null)
                        }].filter(v => v !== null)}/>
                </Sider>}
            <Content {...contentProps}>
                {urlConsent ? <Suspense>
                    <Cookies
                        key={'consent'}
                        render={render}
                        urlConsent={urlConsent}
                        style={{
                            bottom: '16px',
                            left: hideSideMenu ? '16px' : (sliderCollapsed ? '96px' : '216px')
                        }}/>
                </Suspense> : null}
                {mustLogin && !logged ? page403 || <Result
                    status="403"
                    title="403"
                    subTitle={form.t("Sorry, you are not authorized to access this page.")}
                /> : _items.length ? routes.map(({element, path}, index) => {
                    return (visitedRoutes[path] ? <div key={index} style={{
                        display: pathname === path ? "block" : "none",
                        height: "100%",
                        width: "100%"
                    }}>
                        {element}
                    </div> : null)
                }) : children}
                {!mustLogin && ((_items.length && !routes.some(({path}) => path === pathname)) || children === undefined) ?
                    <Suspense fallback={<Skeleton/>}>
                        <ContentPage key={`plasmic-${pathname}`}
                                     homePath={homePath} render={render}/>
                    </Suspense> : null
                }
                {cloudUrl ? <>
                    <CloudDownloadField
                        key={'cloud'}
                        uiSchema={{
                            'ui:cloudUrl': cloudUrl,
                            'ui:modal': {
                                open: openCloudDownload,
                                onCancel: () => {
                                    setOpenCloudDownload(false)
                                }
                            },
                            'ui:currentKey': currentDataId,
                            'ui:onSelect': (data) => {
                                setOpenCloudDownload(false);
                                setCurrentDataId(data)
                            }
                        }}
                        formData={form.state.formData}
                        onChange={form.onChange}
                        formContext={render.formContext}/>
                    <CloudUploadField
                        uiSchema={{
                            'ui:cloudUrl': cloudUrl,
                            'ui:currentKey': currentDataId,
                            'ui:onSave': (data) => {
                                setOpenCloudUpload(false);
                                setCurrentDataId(data)
                            },
                            'ui:modal': {
                                open: openCloudUpload,
                                onCancel: () => {
                                    setOpenCloudUpload(false)
                                }
                            }
                        }}
                        formData={form.state.formData}
                        onChange={form.onChange}
                        formContext={render.formContext}/>
                </> : null}
            </Content>
        </Layout>
        {footer ? <Footer
            key={"footer"}
            style={{
                position: 'sticky',
                bottom: 0,
                zIndex: 1,
                width: '100%',
                padding: '16px 50px',
                textAlign: 'center',
            }}>
            {footer}
        </Footer> : null}
        <FloatButton.Group key={"buttonFloat"}>
            {errors.length && !hideErrors ? (openErrors ?
                <Suspense fallback={<Skeleton/>}><Errors
                    render={render}
                    onClose={() => {
                        setOpenErrors(false)
                    }}
                    open={openErrors}
                /></Suspense>
                : <FloatButton
                    icon={<WarningOutlined/>}
                    badge={{
                        count: errors.length,
                    }}
                    onClick={() => {
                        setOpenErrors(true)
                    }}/>) : null}
            {debugUrl ? (openDebug ? <Drawer
                closable
                placement="left"
                size="large"
                onClose={() => {
                    setOpenDebug(false)
                }}
                open={openDebug}
                key={'debug'}>
                <Suspense fallback={<Skeleton/>}>
                    <Debug render={render}/>
                </Suspense>
            </Drawer> : <FloatButton
                icon={<BugOutlined/>}
                onClick={() => {
                    setOpenDebug(true)
                }}/>) : null}
        </FloatButton.Group>
    </Layout>
};
export default App;