import React, {useEffect, useRef, useState, useMemo} from 'react';
import {useLocation, Link} from 'react-router-dom';
import {
    UploadOutlined,
    CaretRightOutlined,
    BugOutlined,
    LaptopOutlined,
    CompressOutlined,
    DownloadOutlined,
    ReloadOutlined,
    CheckCircleOutlined,
    ExpandOutlined,
    DiffOutlined,
    StopOutlined,
    DeleteOutlined,
    CloudUploadOutlined,
    CloudDownloadOutlined,
    CloudOutlined,
    BranchesOutlined,
    WarningOutlined
} from '@ant-design/icons';
import {
    Layout,
    Menu,
    Flex,
    FloatButton,
    Button,
    List,
    Tooltip,
    Popconfirm,
    Modal,
    Drawer,
    Typography,
    Result
} from 'antd';
import {useFullscreen} from "ahooks";
import exportJSON from "../../../../core/utils/Export"
import uploadJSON from "../../../../core/utils/Import"
import {
    cleanStorage,
    readDiffList,
    storeData,
    buildData
} from "../../../../core/utils/Autosave"
import CloudDownloadField from '../../fields/CloudDownloadField'
import CloudUploadField from '../../fields/CloudUploadField'
import {
    DraggableModal
} from "ant-design-draggable-modal/packages/ant-design-draggable-modal";
import {useLocaleStore} from "../../models/locale";
import isEmpty from "lodash/isEmpty";
import {createLayoutElement} from "../../../../core";
import Errors from "../Errors/Drawer";
import Debug from "../Debug";
import Cookies from '../Cookies'

const DiffViewer = React.lazy(() => import("../../../../core/components/DiffViewer"))
const UserNav = React.lazy(() => import('./User'))
const LanguageNav = React.lazy(() => import('./Language'))
const ContactNav = React.lazy(() => import('./Contact'))
const ContentPage = React.lazy(() => import('./ContentPages'))

const formatItem = ({path, label, children, ...item}) => {
    if (path && typeof label === 'string') {
        label = <Link to={path}>{label}</Link>
    }
    if (children) {
        children = children.map(formatItem)
    }
    return {path, label, children, ...item}
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
        savingData = false,
        savingKey,
        items = [],
        urlContact,
        languages = true,
        logo,
        userProps = {},
        cloudUrl,
        urlConsent,
        hideErrors = false,
        hideNav = false,
        hideRun = false,
        hideDebug = false,
        hideClean = false,
        hideFullscreen = false,
        hideFiles = false,
        hideSideMenu = false,
        footer = null,
        theme = 'light',
        contentProps,
        homePath = '/',
        ...props
    }
) => {
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
    const storeKey = savingKey || (render ? 'schedula-' + form.props.$id + '-' + render.idSchema.$id + '-formData' : 'form')
    const [saving, setSaving] = useState(savingData);
    const {formData} = render;
    const [openRestore, setOpenRestore] = useState(false);
    const [dateDiffViewer, setDateDiffViewer] = useState(null);
    useEffect(function updateStorage() {
        if (saving) {
            try {
                storeData(storeKey, formData)
            } catch (error) {
                setSaving(false)
                form.props.notify({
                    message: locale.autoSavingErrorTitle,
                    description: error.message,
                    type: 'warning'
                })
            }
        }
    }, [storeKey, formData, saving, locale.autoSavingErrorTitle, form.props]);
    const {changes, diffList} = useMemo(function updateDiffList() {
        if (openRestore) {
            return readDiffList(storeKey, formData)
        }
        return {}
    }, [storeKey, formData, openRestore]);
    const oldFormData = useMemo(function updateOldFormData() {
        if (dateDiffViewer !== null && changes) {
            return buildData(changes, dateDiffViewer)
        }
        return null
    }, [changes, dateDiffViewer]);
    const _items = useMemo(() => (items.map(formatItem)), [])
    const {pathname} = useLocation()
    const {routes} = useMemo(() => {
        const routes = [...formatRoutes({children: items}, children)]
        return {routes}
    }, [children, items])

    const [selectedKeys, setSelectedKeys] = useState(null);
    useEffect(() => {
        const _routes = routes.sort((a, b) => (b.path || "").length - (a.path || "").length)
        let {
            key = null
        } = _routes.find(({path}) => pathname === path) || {}
        if (key === null) {
            return null
        } else {
            setSelectedKeys([String(key)])
        }
        return [String(key)]
    }, [])
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
    const [languageOptions, setLanguageOptions] = useState(languages !== true ? languages : null);
    useEffect(() => {
        if (languages === true)
            fetch('/locales', {
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Encoding': 'gzip',
                    'Accept-Encoding': 'gzip'
                }
            }).then(v => v.json()).then((v) => {
                setLanguageOptions(v)
            }).catch((error) => {
                setLanguageOptions(null)
                form.props.notify({message: error})
            })
    }, [languages, form.props]);
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
        const {loginRequired = false} = userProps
        return loginRequired === true || (typeof loginRequired === 'object' && loginRequired[pathname])
    }, [pathname, userProps])

    return <Layout style={{height: '100%'}}>
        {!hideNav || currentDataId || urlContact || languages || userProps || _items.length || logo ?
            <Header
                className={`ant-menu-${theme}`}
                style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 1,
                    width: '100%',
                    padding: 0,
                    display: "flex",
                }}>
                    <div key={'logo'} style={{
                        height: "100%",
                        textAlign: 'center',
                        lineHeight: 'normal'
                    }}>{logo ? createLayoutElement({
                        key: 'logo', layout: logo, render, isArray: false
                    }) : null}</div>
                    {_items.length ? <Menu
                        key={'left-menu'}
                        theme={theme}
                        mode="horizontal"
                        style={{flex: "auto", minWidth: 0}}
                        selectedKeys={selectedKeys}
                        items={_items}
                        onSelect={({key}) => {
                            setSelectedKeys([key])
                        }}
                        {...props}
                    /> : <div style={{flex: "auto", minWidth: 0}}/>}
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
                            {urlContact ? <ContactNav
                                form={form}
                                formContext={formContext}
                                containerRef={mainLayout}
                                urlContact={urlContact}/> : null}
                            {languageOptions ? <LanguageNav
                                form={form}
                                languages={languageOptions}/> : null}
                            {userProps ?
                                <UserNav
                                    form={form}
                                    formContext={formContext}
                                    containerRef={mainLayout}
                                    {...userProps}/> : null}
                        </Flex> : null}
            </Header> : null}
        <Layout ref={mainLayout} style={{
            position: 'relative'
        }}>
            {hideSideMenu || (hideRun && hideDebug && hideClean && hideFullscreen && !cloudUrl && hideFiles && !savingData) ? null :
                <Sider collapsible onCollapse={(collapsed) => {
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
                            } else if (key === 'upload') {
                                impButton.current.click()
                            } else if (key === 'autosave') {
                                setSaving(!saving)
                            } else if (key === 'restore') {
                                setOpenRestore(!openRestore)
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
                                }
                            ]
                        }, !savingData ? null : {
                            icon: <BranchesOutlined/>,
                            key: 'branches',
                            className: 'branches-button',
                            label: locale.branchesButton,
                            children: [
                                {
                                    icon: saving ? <CheckCircleOutlined/> :
                                        <StopOutlined/>,
                                    key: 'autosave',
                                    className: 'autosave-button',
                                    label: <Tooltip
                                        title={saving ? locale.autoSavingTooltip :
                                            locale.autoSaveTooltip}
                                        placement="right">
                                        {saving ? locale.autoSavingButton : locale.autoSaveButton}
                                    </Tooltip>
                                },
                                {
                                    icon: <ReloadOutlined/>,
                                    key: 'restore',
                                    className: 'restore-button',
                                    label: <Tooltip
                                        title={locale.restoreTooltip}
                                        placement="right">
                                        {locale.restoreButton}
                                    </Tooltip>
                                }
                            ]
                        }].filter(v => v !== null)}/>
                </Sider>}
            <Content {...contentProps}>
                {urlConsent ? <Cookies
                    render={render}
                    urlConsent={urlConsent}
                    style={{
                        bottom: '16px',
                        left: hideSideMenu ? '16px' : (sliderCollapsed ? '96px' : '216px')
                    }}/> : null}
                {mustLogin && !logged ? <Result
                    status="403"
                    title="403"
                    subTitle="Sorry, you are not authorized to access this page."
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
                    <ContentPage homePath={homePath} render={render}/> : null
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
                <DraggableModal
                    key={'restore'}
                    title={locale.restoreModalTitle}
                    open={openRestore}
                    onOk={() => {
                        setOpenRestore(false)
                    }}
                    onCancel={() => {
                        setOpenRestore(false)
                    }}
                    footer={[
                        <Button key="erase"
                                onClick={() => {
                                    setOpenRestore(false);
                                    cleanStorage(storeKey)
                                }}>{locale.restoreEraseButton}</Button>,
                        <Button key="close"
                                onClick={() => {
                                    setOpenRestore(false);
                                }}>{locale.restoreCloseButton}</Button>
                    ]}>
                    <List
                        size="small"
                        dataSource={diffList}
                        renderItem={(item) => (
                            <List.Item>
                                <List.Item.Meta
                                    avatar={
                                        <Popconfirm
                                            title={locale.restoreConfirm}
                                            placement="top"
                                            onConfirm={(event) => {
                                                if (event) {
                                                    event.preventDefault();
                                                }
                                                render.parent.props.onChange(buildData(changes, item.date))
                                                setOpenRestore(false)
                                            }}>
                                            <Button
                                                type="primary"
                                                shape="circle"
                                                icon={
                                                    <ReloadOutlined/>}
                                            />
                                        </Popconfirm>
                                    }
                                    title={(new Date(item.date * 60000)).toLocaleString()}
                                />
                                {item.sameAsCurrent ? null :
                                    <Tooltip
                                        title={locale.restoreDifferences}
                                        placement="bottom">
                                        <Button
                                            type="primary"
                                            shape="circle"
                                            icon={
                                                <DiffOutlined/>}
                                            onClick={() => {
                                                setDateDiffViewer(item.date)
                                            }}/>
                                    </Tooltip>}
                            </List.Item>
                        )}
                    />
                </DraggableModal>
                <DraggableModal
                    key={'diff'}
                    title={locale.restoreTitleDifferences}
                    open={dateDiffViewer !== null}
                    onCancel={() => {
                        setDateDiffViewer(null)
                    }}
                    footer={[
                        <Button key="restore"
                                onClick={() => {
                                    setOpenRestore(false);
                                    render.parent.props.onChange(oldFormData)
                                    setDateDiffViewer(null);
                                }}>{locale.restoreRestoreButton}</Button>,
                        <Button key="close"
                                onClick={() => {
                                    setDateDiffViewer(null);
                                }}>{locale.restoreCloseButton}</Button>
                    ]}>
                    {dateDiffViewer ? <DiffViewer
                        rightTitle={(new Date(Math.floor(Date.now() / 60000) * 60000)).toLocaleString() + ` (${locale.restoreCurrent})`}
                        leftTitle={(new Date(dateDiffViewer * 60000)).toLocaleString()}
                        oldValue={oldFormData}
                        newValue={formData}/> : null}
                </DraggableModal>
            </Content>
        </Layout>
        {
            footer ? <Footer
                style={{
                    position: 'sticky',
                    bottom: 0,
                    zIndex: 1,
                    width: '100%',
                    padding: '16px 50px',
                    textAlign: 'center',
                }}>
                {footer}
            </Footer> : null
        }
        <FloatButton.Group>
            {errors.length && !hideErrors ? (openErrors ?
                <Errors render={render}
                        onClose={() => {
                            setOpenErrors(false)
                        }}
                        open={openErrors}/>
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
                <Debug render={render}/>
            </Drawer> : <FloatButton
                icon={<BugOutlined/>}
                onClick={() => {
                    setOpenDebug(true)
                }}/>) : null}
        </FloatButton.Group>
    </Layout>
};
export default App;