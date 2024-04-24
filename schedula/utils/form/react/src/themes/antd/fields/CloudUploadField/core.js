import {
    SaveOutlined,
    CloudUploadOutlined,
    PlusOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../models/locale";
import qs from 'qs';
import React, {useEffect, useState} from 'react';
import {
    Button,
    Form,
    Input,
    Spin,
    Space,
    Modal,
    Typography
} from 'antd';
import {getUiOptions} from "@rjsf/utils";
import post from "../../../../core/utils/fetch";
import isEqual from "lodash/isEqual";


export default function CloudUploadField({uiSchema, formData, formContext}) {
    const {form} = formContext
    const {getLocale} = useLocaleStore()
    const locale = getLocale('CloudUploadField')
    const {
        cloudUrl = '/item',
        button = false,
        onSave,
        modal,
        currentKey: _currentKey,
    } = getUiOptions(uiSchema);
    const [openSave, setOpenSave] = useState(!(button || modal));
    const props = {
        open: openSave,
        onCancel: () => {
            setOpenSave(false)
        },
        ...modal
    }
    const [_form] = Form.useForm();
    const [currentKey, setCurrentKey] = useState(null);
    const [loading, setLoading] = useState(false);
    const postUpdate = (data, method, name, id) => {
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
                    description: (data.errors || [data.error]).join('\n'),
                })
            } else {
                const {id, name} = data
                setCurrentKey({id, name})
                props.onCancel()
                if (onSave)
                    onSave({id, name, data: formData})
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
        try {
            const row = await _form.validateFields();
            if (id !== undefined) {
                postUpdate(formData, 'PUT', row['new-name'], id)
            } else {  // post
                postUpdate(formData, 'POST', row['new-name'])
            }
        } catch (errInfo) {
        }
    };
    useEffect(() => {
        if (!isEqual(_currentKey, currentKey))
            setCurrentKey(_currentKey)
    }, [_currentKey])
    let content = <Form key={'form'} form={_form} component={false}>
        <Spin spinning={loading}>
            <Modal
                title={locale.titleSaveNew}
                footer={<div style={{display: "flex"}}>
                    {currentKey ? <Space
                        key={'left'} style={{flex: "auto", minWidth: 0}}>
                        <Button type="primary" ghost icon={<SaveOutlined/>}
                                onClick={(event) => {
                                    event.stopPropagation();
                                    handleUpdate(currentKey.id);
                                }}>
                            {locale.buttonOverwrite}
                        </Button>
                        <Typography.Text keyboard>
                            # {currentKey.id} - {currentKey.name}
                        </Typography.Text>
                    </Space> : <div style={{flex: "auto", minWidth: 0}}/>}
                    <div style={{paddingLeft: '16px'}}>
                        <Space>
                            <Button type="primary" ghost
                                    icon={<PlusOutlined/>} onClick={(event) => {
                                event.stopPropagation();
                                handleUpdate()
                            }}>
                                {locale.buttonSaveNew}
                            </Button>
                            <Button type="primary" ghost onClick={(event) => {
                                event.stopPropagation();
                                props.onCancel()
                            }}>
                                {locale.buttonCancel}
                            </Button>
                        </Space>
                    </div>
                </div>}
                {...props}>
                <Form.Item
                    name='new-name'
                    label={locale.titleName}
                    style={{margin: 0}}
                    rules={[{
                        required: true,
                        message: locale.fieldErrors.name
                    }]}>
                    <Input/>
                </Form.Item>
            </Modal>
        </Spin>
    </Form>
    if (button) {
        return [
            <Button key={'button'} icon={<CloudUploadOutlined/>}
                    type={'primary'}
                    shape="circle"
                    onClick={(event) => {
                        event.stopPropagation();
                        setOpenSave(true)
                    }} {...button}/>,
            content
        ]
    } else {
        return content
    }
};