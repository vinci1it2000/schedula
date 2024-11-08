import {
    Avatar,
    Badge,
    Button,
    Divider,
    Flex,
    Form,
    Input,
    Space,
    Spin
} from 'antd'
import {useState, useMemo, useCallback, useEffect} from "react";
import {
    IdcardOutlined,
    SaveOutlined,
    ReloadOutlined,
    UserOutlined,
    MailOutlined,
    EditOutlined,
    CloseOutlined,
    CloseCircleOutlined,
    UploadOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import isEqual from "lodash/isEqual";
import pick from "lodash/pick"
import {useDropzone} from 'react-dropzone';
import omit from "lodash/omit";
import omitBy from "lodash/omitBy";
import isUndefined from "lodash/isUndefined"

export default function InfoForm(
    {
        render: {formContext: {form}},
        urlEdit,
        addUsername = false,
        customData
    }) {
    const {state: {userInfo}} = form
    const [spinning, setSpinning] = useState(false);
    const [editing, setEditing] = useState(false);
    const [field_errors, setFieldErrors] = useState({});
    const [initialValues, setInitialValues] = useState({})
    const [userImage, setUserImage] = useState(null);
    const [edited, setEdited] = useState({})
    const {getRootProps, getInputProps} = useDropzone({
        maxSize: 500000,
        maxFiles: 1,
        accept: {
            'image/png': ['.png'],
            'image/jpeg': ['.jpg', '.jpeg'],
        },
        onError: (error) => {
            form.props.notify(error)
        },
        onDrop: (acceptedFiles, fileRejections = []) => {
            if (fileRejections.length > 0) {
                let fileErrors = []
                fileRejections.forEach(({errors}) => {
                    errors.forEach(({message}) => {
                        fileErrors.push(message)
                    })
                })
                setFieldErrors({
                    ...field_errors,
                    avatar: [...new Set(fileErrors)].join(' ')
                })
            } else {
                const reader = new FileReader();
                reader.onload = function (e) {
                    const base64URL = e.target.result;
                    setUserImage(base64URL);
                    setEdited((edited) => ({...edited, avatar: base64URL}))
                    if (field_errors.avatar)
                        setFieldErrors({...field_errors, avatar: undefined})
                };
                reader.readAsDataURL(acceptedFiles[0]);
            }
        }
    });
    const [_form] = Form.useForm();
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Setting')
    useEffect(() => {
        let {
            custom_data,
            ...values
        } = pick(userInfo, [
            'firstname', 'lastname', 'avatar', 'email', 'username', 'custom_data'
        ]);
        values = {...values, ...custom_data}
        setUserImage(values.avatar)
        setInitialValues(values)
        setEdited(values)
        _form.setFieldsValue(values)
    }, [userInfo])
    const onReset = useCallback(() => {
        setEdited((edited) => ({...edited, avatar: null}))
        setUserImage(null);
        if (field_errors.avatar)
            setFieldErrors({...field_errors, avatar: undefined})
    }, []);
    const modified = useMemo(() => {
        return !isEqual(omitBy(edited, isUndefined), omitBy(initialValues, isUndefined))
    }, [edited, initialValues])

    const onFinish = useCallback((data) => {
        setSpinning(true)
        const customDataKeys = (customData || []).map(({name}) => name)
        const newData = omit(data, customDataKeys);
        newData.custom_data = pick(data, customDataKeys)
        form.postData({
            url: urlEdit,
            data: newData
        }, ({data: {response: {user = {}}}}) => {
            setSpinning(false)
            form.setState((state) => ({
                ...state,
                userInfo: user,
                submitCount: state.submitCount + 1
            }))
            setEditing(false)
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlEdit, customData])
    return <Spin spinning={spinning}>
        <Form
            layout="vertical"
            key={'form'}
            form={_form}
            disabled={!editing}
            style={{
                maxWidth: '300px',
                width: '100%',
                margin: 'auto',
                paddingBottom: '15px'
            }}
            initialValues={initialValues}
            onValuesChange={(_, allValues) => {
                setEdited((edited) => ({...edited, ...allValues}))
            }}
            onFinish={(data) => onFinish({...data, avatar: userImage})}>
            <Form.Item
                name="avatar"
                validateStatus={field_errors.avatar ? "error" : undefined}
                help={field_errors.avatar}>
                <Flex gap="middle" justify="space-between">
                    {editing ? <Flex key={'avatar-editing'} gap="middle"
                                     align="center">
                            <div
                                key={'avatar-upload'} {...getRootProps({className: 'dropzone'})}>
                                <input {...getInputProps()} />
                                <label htmlFor='icon-button-file'>
                                    <Badge
                                        count={userImage ?
                                            <CloseCircleOutlined
                                                onClick={(event) => {
                                                    event.stopPropagation()
                                                    onReset()
                                                }}/>
                                            :
                                            <UploadOutlined
                                                style={{cursor: 'pointer'}}/>}>
                                        <Avatar
                                            style={{cursor: 'pointer'}}
                                            src={userImage} size={64}
                                            icon={<UserOutlined/>}
                                        />
                                    </Badge>
                                </label>
                            </div>
                        </Flex> :
                        <Avatar
                            key={'avatar'}
                            style={{cursor: 'not-allowed'}}
                            src={userImage}
                            size={64} icon={<UserOutlined/>}/>
                    }
                    <Button
                        key={'controls'}
                        type={editing ? "danger" : "primary"}
                        shape="circle"
                        disabled={false}
                        icon={editing ? <CloseOutlined/> : <EditOutlined/>}
                        onClick={() => {
                            if (editing) {
                                _form.setFieldsValue(initialValues)
                                setUserImage(initialValues.avatar)
                            } else {
                                _form.setFieldsValue(edited)
                                setUserImage(edited.avatar)
                            }
                            setEditing(!editing)
                        }}
                    />
                </Flex>
            </Form.Item>
            <Form.Item
                label={locale.labelName}
                name="firstname"
                validateStatus={field_errors.firstname ? "error" : undefined}
                help={field_errors.firstname}
                rules={[{
                    required: true,
                    message: locale.firstnameRequired
                }]}>
                <Input
                    prefix={<IdcardOutlined
                        className="site-form-item-icon"/>}
                    placeholder={locale.firstnamePlaceholder}
                    onChange={() => {
                        if (field_errors.firstname)
                            setFieldErrors({
                                ...field_errors,
                                firstname: undefined
                            })
                    }}/>
            </Form.Item>
            <Form.Item
                label={locale.labelSurname}
                name="lastname"
                validateStatus={field_errors.lastname ? "error" : undefined}
                help={field_errors.lastname}
                rules={[{
                    required: true,
                    message: locale.lastnameRequired
                }]}>
                <Input
                    prefix={<IdcardOutlined
                        className="site-form-item-icon"/>}
                    placeholder={locale.lastnamePlaceholder}
                    onChange={() => {
                        if (field_errors.lastname)
                            setFieldErrors({
                                ...field_errors,
                                lastname: undefined
                            })
                    }}/>
            </Form.Item>
            {!editing && userInfo.email ? <Form.Item
                name="email" label={locale.labelEmail}>
                <Input prefix={
                    <MailOutlined className="site-form-item-icon"/>
                }/>
            </Form.Item> : null}
            {addUsername && !editing && userInfo.username ?
                <Form.Item label={locale.labelUsername} name="username">
                    <Input
                        prefix={<UserOutlined
                            className="site-form-item-icon"/>}/>
                </Form.Item> : null}
            {customData ?
                <Divider plain>{locale.titleCustomData}</Divider> : null}
            {(customData || []).map(({name, itemProps, inputProps}) =>
                <Form.Item
                    name={name}
                    validateStatus={field_errors[name] ? "error" : undefined}
                    help={field_errors[name]}
                    {...itemProps}>
                    <Input {...inputProps} onChange={() => {
                        if (field_errors[name])
                            setFieldErrors({
                                ...field_errors,
                                [name]: undefined
                            })
                    }}/>
                </Form.Item>)}
            <Form.Item>
                {!editing ? null :
                    <Space>
                        <Button type="primary" htmlType="submit"
                                disabled={!modified}
                                icon={<SaveOutlined/>}>
                            {locale.submitButton}
                        </Button>
                        <Button icon={<ReloadOutlined/>} onClick={() => {
                            _form.setFieldsValue(initialValues)
                            setUserImage(initialValues.avatar)
                            setEdited(initialValues)
                        }} disabled={!modified}>
                            {locale.revertButton}
                        </Button>
                    </Space>
                }
            </Form.Item>
        </Form>
    </Spin>
}