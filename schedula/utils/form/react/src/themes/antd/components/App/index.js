import React, {useEffect, useRef, useState, useMemo} from 'react';
import {
    UploadOutlined,
    CaretRightOutlined,
    BugOutlined,
    SaveOutlined,
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
    CloudOutlined
} from '@ant-design/icons';
import {
    Layout,
    Menu,
    FloatButton,
    Button,
    List,
    Tooltip,
    Popconfirm,
    Space,
    Modal,
    Tabs,
    Typography
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
import {DraggableModal} from "ant-design-draggable-modal";
import {useLocaleStore} from "../../models/locale";
import './App.css'
import isEmpty from "lodash/isEmpty";

const DiffViewer = React.lazy(() => import("../../../../core/components/DiffViewer"))
const UserNav = React.lazy(() => import('./User'))
const LanguageNav = React.lazy(() => import('./Language'))
const ContactNav = React.lazy(() => import('./Contact'))

const {Header, Content, Footer, Sider} = Layout,
    App = ({
               children,
               render,
               savingData = true,
               savingKey,
               items = [],
               defaultSelectedKeys = ["0"],
               urlContact,
               userProps,
               cloudUrl,
               hideRun = false,
               hideDebug = false,
               hideSideMenu = false,
               footer = null,
               theme = 'dark',
               contentProps,
               ...props
           }) => {
        const {getLocale} = useLocaleStore()
        const locale = getLocale('App')
        const impButton = useRef(null);
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
        }, [storeKey, formData, saving, locale.autoSavingErrorTitle]);
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
        const formatItem = (item) => {
            if (item.href && typeof item.label === 'string') {
                item.label = <a href={item.href}>{item.label}</a>
            }
            if (item.children) {
                item.children = item.children.map(formatItem)
            }
            return item
        }
        const _items = items.map(formatItem)
        const [indexContent, setIndexContent] = useState(defaultSelectedKeys[0]);
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
        return <Layout style={{height: '100%'}} {...props}>
            {hideSideMenu ? null :
                <Sider collapsible defaultCollapsed={true} style={{
                    overflowY: "auto",
                    marginBottom: "48px"
                }} theme={theme}>
                    <div style={{
                        height: 32,
                        margin: 16,
                        background: 'rgba(255, 255, 255, 0.2)',
                    }}/>
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
                                form.submit()
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
                            key: 'run',
                            label: locale.runButton
                        }, hideDebug ? null : {
                            icon: <BugOutlined/>,
                            key: 'debug',
                            label: locale.debugButton
                        }, {
                            icon: <DeleteOutlined/>,
                            key: 'clean',
                            label: locale.cleanButton
                        }, isFullscreenEnabled ? {
                            icon: isFullscreen ? <CompressOutlined/> :
                                <ExpandOutlined/>,
                            key: 'fullscreen',
                            label: <Tooltip
                                title={isFullscreen ? locale.disableFullscreen : locale.enableFullscreen}
                                placement="right">
                                {locale.fullscreenButton}
                            </Tooltip>
                        } : null, logged && cloudUrl ? {
                            icon: <CloudOutlined/>,
                            key: 'cloud',
                            label: locale.cloudButton,
                            children: [
                                {
                                    icon: <CloudDownloadOutlined/>,
                                    key: 'cloud-download',
                                    label: <Tooltip
                                        title={locale.cloudDownloadTooltip}
                                        placement="right">
                                        {locale.cloudDownloadButton}
                                    </Tooltip>
                                },
                                {
                                    icon: <CloudUploadOutlined/>,
                                    key: 'cloud-upload',
                                    label: <Tooltip
                                        title={locale.cloudUploadTooltip}
                                        placement="right">
                                        {locale.cloudUploadButton}
                                    </Tooltip>
                                }
                            ]
                        } : null, {
                            icon: <SaveOutlined/>,
                            key: 'files',
                            label: locale.filesButton,
                            children: [
                                {
                                    icon: <DownloadOutlined/>,
                                    key: 'download',
                                    label: <Tooltip
                                        title={locale.downloadTooltip}
                                        placement="right">
                                        {locale.downloadButton}
                                    </Tooltip>
                                },
                                {
                                    icon: <UploadOutlined/>,
                                    key: 'upload',
                                    label: <Tooltip
                                        title={locale.uploadTooltip}
                                        placement="right">
                                        {locale.uploadButton}
                                    </Tooltip>
                                },
                                {
                                    icon: saving ? <CheckCircleOutlined/> :
                                        <StopOutlined/>,
                                    key: 'autosave',
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
                                    label: <Tooltip
                                        title={locale.restoreTooltip}
                                        placement="right">
                                        {locale.restoreButton}
                                    </Tooltip>
                                }
                            ]
                        }].filter(v => v !== null)}/>
                </Sider>}
            <Layout>
                <Header
                    style={{
                        position: 'sticky',
                        top: 0,
                        zIndex: 1,
                        width: '100%',
                        padding: 0
                    }}>
                    <div style={{display: "flex"}}>
                        {_items.length ? <Menu
                            key={'left-menu'}
                            theme={theme}
                            mode="horizontal"
                            style={{flex: "auto", minWidth: 0}}
                            defaultSelectedKeys={defaultSelectedKeys}
                            items={_items}
                            onSelect={({key}) => {
                                setIndexContent(key)
                            }}
                            {...props}
                        /> : <div style={{flex: "auto", minWidth: 0}}/>}
                        <Space key={'right-element'}
                               className={`ant-menu-${theme} css-dev-only-do-not-override-j0nf2s`}
                               style={{
                                   paddingLeft: '16px',
                                   paddingRight: '16px',
                                   cursor: 'pointer'
                               }}>
                            {currentDataId ? <Typography.Text keyboard>
                                # {currentDataId.id} - {currentDataId.name}
                            </Typography.Text> : null}
                            <ContactNav form={form} formContext={formContext}
                                        urlContact={urlContact}/>
                            <LanguageNav form={form}/>
                            {userProps ?
                                <UserNav form={form} {...userProps}/> : null}
                        </Space>
                    </div>
                </Header>
                <Content style={{margin: '16px 16px'}} {...contentProps}>
                    {_items.length ? <Tabs
                        activeKey={String(indexContent)}
                        items={children.map((child, index) => ({
                            key: String(index),
                            children: child,
                            style: {height: "100%"}
                        }))}
                        renderTabBar={() => null}
                        style={{height: '100%'}}
                    /> : children}
                    <FloatButton.BackTop/>
                    {cloudUrl ? <>
                        <CloudDownloadField
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
                        title={locale.restoreModalTitle}
                        open={openRestore}
                        onOk={() => {
                            setOpenRestore(false)
                        }}
                        onCancel={() => {
                            setOpenRestore(false)
                        }}
                        footer={[
                            <Button key="erase" onClick={() => {
                                setOpenRestore(false);
                                cleanStorage(storeKey)
                            }}>{locale.restoreEraseButton}</Button>,
                            <Button key="close" onClick={() => {
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
                                                    icon={<ReloadOutlined/>}
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
                                                icon={<DiffOutlined/>}
                                                onClick={() => {
                                                    setDateDiffViewer(item.date)
                                                }}/>
                                        </Tooltip>
                                    }
                                </List.Item>
                            )}
                        />
                    </DraggableModal>
                    <DraggableModal
                        title={locale.restoreTitleDifferences}
                        open={dateDiffViewer !== null}
                        onCancel={() => {
                            setDateDiffViewer(null)
                        }}
                        footer={[
                            <Button key="restore" onClick={() => {
                                setOpenRestore(false);
                                render.parent.props.onChange(oldFormData)
                                setDateDiffViewer(null);
                            }}>{locale.restoreRestoreButton}</Button>,
                            <Button key="close" onClick={() => {
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
                {footer ? <Footer
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
            </Layout>
        </Layout>
    };
export default App;