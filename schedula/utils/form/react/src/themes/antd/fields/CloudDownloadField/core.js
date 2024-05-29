import {
    EditOutlined,
    SelectOutlined,
    DeleteOutlined,
    CheckOutlined,
    CloseOutlined,
    SaveOutlined,
    DownloadOutlined,
    CloudOutlined,
    PlusOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../models/locale";
import qs from 'qs';
import React, {useEffect, useState, useCallback} from 'react';
import {
    Button,
    Form,
    Input,
    Popconfirm,
    Table,
    Space,
    Switch,
    Modal,
    Typography
} from 'antd';
import {getUiOptions} from "@rjsf/utils";
import post from "../../../../core/utils/fetch";
import isEqual from "lodash/isEqual";
import isArray from "lodash/isArray";
import get from "lodash/get";
import exportJSON from "../../../../core/utils/Export";


export default function CloudDownloadField(
    {uiSchema, formData, onChange, formContext}) {
    const {form} = formContext
    const {getLocale} = useLocaleStore()
    const locale = getLocale('CloudDownloadField')
    let {
        cloudUrl = '/item',
        modal,
        button = false,
        onSelect,
        postGet,
        objectItems,
        currentKey: _currentKey,
        ...props
    } = getUiOptions(uiSchema);

    const [_form] = Form.useForm();
    const [editingKey, setEditingKey] = useState('');
    const [currentKey, setCurrentKey] = useState(null);
    const [openSave, setOpenSave] = useState(false);
    const [openModal, setOpenModal] = useState(!(button || modal));
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);
    const cancel = () => {
        setEditingKey('');
    };
    if (isArray(objectItems))
        objectItems = objectItems.reduce((r, k) => {
            r[k] = k;
            return r
        }, {})
    const [tableParams, setTableParams] = useState({
        pagination: {
            current: 1,
            pageSize: 10,
            onChange: cancel,
            hideOnSinglePage: true,
            showQuickJumper: true
        }
    });

    const EditableCell = (
        {editing, dataIndex, title, record, index, children, ...restProps}) => {
        return <td {...restProps}>
            {editing ? <Form.Item
                name={dataIndex}
                style={{margin: 0}}
                rules={[{required: true, message: locale.fieldErrors[title]}]}>
                {dataIndex === 'data' ?
                    <Switch checkedChildren={locale.dataSwitchChecked}
                            unCheckedChildren={locale.dataSwitchUnChecked}/>
                    : <Input/>}
            </Form.Item> : children}
        </td>
    };
    const isEditing = (record) => record.id === editingKey;
    const edit = (record) => {
        _form.setFieldsValue({
            name: '',
            data: false,
            ...record,
        });
        setEditingKey(record.id);
    };
    const fetchData = useCallback(() => {
        setLoading(true);
        const query = qs.stringify({
            page: tableParams.pagination.current || 1,
            per_page: tableParams.pagination.pageSize || 10
        })
        post({
            url: `${cloudUrl}?${query}`,
            data: {},
            form,
            method: 'GET'
        }).then(({data, messages}) => {
            setLoading(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
            } else {
                const {page, total, items} = data
                setData(items);
                setLoading(false);
                setTableParams({
                    ...tableParams,
                    pagination: {
                        ...tableParams.pagination,
                        total: total,
                        current: page
                    }
                });
            }
        }).catch(error => {
            setLoading(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })
    }, [cloudUrl, form, locale.errorTitle, tableParams]);
    const handleTableChange = (pagination, filters, sorter) => {
        let newParams = {
            pagination,
            filters,
            ...sorter
        }
        if (!isEqual(newParams, tableParams)) {
            setTableParams(newParams);
            fetchData()
        }
    };
    const handleDelete = (id) => {
        setLoading(true)
        post({
            url: `${cloudUrl}/${id}`, data: {}, form, method: 'DELETE'
        }).then(({data, messages}) => {
            setLoading(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
            } else {
                fetchData()
            }
        }).catch(error => {
            setLoading(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })
    };
    const postUpdate = (data, method, name, id, updateCurrent = false) => {
        const query = qs.stringify({name})
        const url = id === undefined ? cloudUrl : `${cloudUrl}/${id}`
        return post({
            url: `${url}?${query}`, data, form, method
        }).then(({data, messages}) => {
            setLoading(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n')
                })
            } else {
                setOpenSave(false)
                if (updateCurrent) {
                    const {id, name} = data
                    setCurrentKey({id, name})
                    if (onSelect)
                        onSelect({id, name, data: formData})
                }
                fetchData()
            }
        }).catch(error => {
            setLoading(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })
    }
    const handleUpdate = async (id) => {
        cancel()
        let data = formData
        if (objectItems) {
            data = Object.entries(objectItems).reduce((res, [pathFrom, pathTo]) => {
                res[pathTo] = get(formData, pathFrom)
                return res
            }, {})
        }
        try {
            const row = await _form.validateFields();
            if (id !== undefined) {
                if (row.data) {  //put
                    postUpdate(data, 'PUT', row.name, id)
                } else {  //patch
                    postUpdate({}, 'PATCH', row.name, id)
                }
            } else if (openSave === 2) {
                postUpdate(data, 'PUT', row['new-name'], currentKey.id, true)
            } else {  // post
                postUpdate(data, 'POST', row['new-name'], undefined, true)
            }
        } catch (errInfo) {
        }
    };
    const handleGet = (id) => {
        cancel()
        setLoading(true);
        post({
            url: `${cloudUrl}/${id}`,
            data: {},
            form,
            method: 'GET'
        }).then(({data, messages}) => {
            setLoading(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
            } else {
                let {
                    id,
                    name,
                    data: _data
                } = postGet ? form.compileFunc(postGet)({
                    ...data,
                    formData
                }) : data
                if (objectItems) {
                    _data = Object.entries(objectItems).reduce((res, [pathFrom, pathTo]) => {
                        res[pathFrom] = get(_data, pathTo)
                        return res
                    }, {...formData})
                }
                setCurrentKey({id, name})
                onChange(_data)
                setOpenModal(false)
                if (onSelect)
                    onSelect(data)
            }
        }).catch(error => {
            setLoading(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })
    };
    const handleDownload = (id) => {
        setLoading(true);
        post({
            url: `${cloudUrl}/${id}`,
            data: {},
            form,
            method: 'GET'
        }).then(({data, messages}) => {
            setLoading(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
            } else {
                const {name, data: _data} = data
                exportJSON(_data, `${name}.json`)
            }
        }).catch(error => {
            setLoading(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })

    };
    useEffect(() => {
        if (openModal || (modal || {}).open)
            fetchData();
    }, [openModal, modal, fetchData]);
    useEffect(() => {
        if (!isEqual(_currentKey, currentKey))
            setCurrentKey(_currentKey)
    }, [_currentKey])
    const columns = [
        {
            dataIndex: 'select',
            fixed: 'left',
            render: (_, record) => (<Button
                type="primary" shape="circle" icon={<SelectOutlined/>} ghost
                onClick={(event) => {
                    event.stopPropagation();
                    handleGet(record.id)
                }}/>),
            width: 48,
        }, {
            title: '#',
            dataIndex: 'id',
            fixed: 'left',
            width: 48
        }, {
            title: locale.titleName,
            dataIndex: 'name',
            editable: true
        }, {
            title: locale.createdAt,
            width: 250,
            dataIndex: 'created_at'
        }, {
            title: locale.updatedAt,
            width: 250,
            dataIndex: 'updated_at'
        }, {
            title: locale.titleData,
            dataIndex: 'data',
            editable: true,
            width: 120,
            render: (_, record) => (<Button
                type="primary" icon={<DownloadOutlined/>}
                onClick={(event) => {
                    event.stopPropagation();
                    handleDownload(record.id)
                }} ghost>
                {locale.buttonDownload}
            </Button>)
        }, {
            fixed: 'right',
            width: 88,
            dataIndex: 'operation',
            render: (_, record) => (isEditing(record) ? <Space>
                <Button type="primary" shape="circle" icon={<CheckOutlined/>}
                        onClick={(event) => {
                            event.stopPropagation();
                            handleUpdate(record.id)
                        }} ghost/>
                <Button danger shape="circle" ghost
                        icon={<CloseOutlined/>} onClick={(event) => {
                    event.stopPropagation();
                    cancel()
                }}/>
            </Space> : <Space>
                <Button type="primary" shape="circle" icon={<EditOutlined/>}
                        onClick={(event) => {
                            event.stopPropagation();
                            edit(record)
                        }} ghost/>
                <Popconfirm title={locale.confirmDelete}
                            onConfirm={(event) => {
                                event.stopPropagation();
                                handleDelete(record.id)
                            }}>
                    <Button danger shape="circle" ghost
                            icon={<DeleteOutlined/>}/>
                </Popconfirm>
            </Space>)
        }
    ];
    const mergedColumns = columns.map((col) => (col.editable ? {
        ...col,
        onCell: (record) => ({
            record, dataIndex: col.dataIndex, title: col.title,
            editing: isEditing(record)
        })
    } : col));
    let content = <Table
        title={() => (<div style={{display: "flex"}}>
            {currentKey ? <Space
                key={'left'} style={{flex: "auto", minWidth: 0}}>
                <Button type="primary" ghost icon={<SaveOutlined/>}
                        onClick={(event) => {
                            event.stopPropagation();
                            setOpenSave(2);
                        }}>
                    {locale.buttonOverwrite}
                </Button>
                <Typography.Text keyboard>
                    # {currentKey.id} - {currentKey.name}
                </Typography.Text>
            </Space> : <div style={{flex: "auto", minWidth: 0}}/>}
            <div style={{paddingLeft: '16px', paddingRight: '16px'}}>
                <Space>
                    <Button type="primary" ghost
                            icon={<PlusOutlined/>} onClick={(event) => {
                        event.stopPropagation();
                        setOpenSave(true);
                    }}>
                        {locale.buttonSaveNew}
                    </Button>
                </Space>
            </div>
        </div>)}
        size={'small'}
        components={{body: {cell: EditableCell}}}
        dataSource={data}
        columns={mergedColumns}
        rowClassName="editable-row"
        rowKey={(record) => record.id}
        pagination={tableParams.pagination}
        loading={loading}
        onChange={handleTableChange}
        {...props}
    />
    if (modal || button) {
        content = <Modal
            key={'modal'} centered width={'90%'} footer={null} open={openModal}
            onCancel={(event) => {
                event.stopPropagation()
                setOpenModal(false)
            }} {...modal}>{content}</Modal>
    }
    content = <Form key={'form'} form={_form} component={false}>
        {content}
        <Modal
            key={'save'}
            open={openSave}
            title={locale.titleSaveNew}
            okText={locale.buttonSave}
            cancelText={locale.buttonCancel}
            onCancel={(event) => {
                event.stopPropagation();
                setOpenSave(false)
            }}
            onOk={(event) => {
                event.stopPropagation();
                handleUpdate()
            }}>
            <Form.Item
                name='new-name'
                label={locale.titleName}
                style={{margin: 0}}
                rules={[{
                    required: true,
                    message: locale.fieldErrors.name,
                }]}>
                <Input/>
            </Form.Item>
        </Modal>
    </Form>

    if (button) {
        return [
            <Button key={'button'} icon={<CloudOutlined/>} type={'primary'}
                    shape="circle"
                    onClick={(event) => {
                        event.stopPropagation();
                        setOpenModal(true)
                    }} {...button}/>,
            content
        ]
    } else {
        return content
    }
};