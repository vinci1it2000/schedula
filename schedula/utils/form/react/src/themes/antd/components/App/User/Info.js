import {
    Avatar,
    Button,
    Flex,
    Form,
    Input,
    Segmented,
    Space
} from 'antd'
import {useState, useMemo, useCallback} from "react";
import {
    IdcardOutlined,
    SaveOutlined,
    ReloadOutlined,
    UserOutlined,
    MailOutlined,
    EditOutlined,
    BulbOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import isEqual from "lodash/isEqual";
import pick from "lodash/pick"
import {useDropzone} from 'react-dropzone';

export default function InfoForm(
    {form, userInfo, urlEdit, setSpinning}) {
    const [disabled, setDisabled] = useState(true);
    const [field_errors, setFieldErrors] = useState({});
    const [_form] = Form.useForm();
    const onFinish = (data) => {
        setSpinning(true)
        form.postData({
            url: urlEdit,
            data: {...data, avatar: userImage},
        }).then(({data: {error, errors, field_errors, response}}) => {
            setSpinning(false)
            if (error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (errors || [error]).join('\n'),
                })
                if (field_errors) {
                    setFieldErrors(field_errors || {})
                }
            } else {
                const {user = {}} = response
                form.setState((state) => ({
                    ...state,
                    userInfo: user,
                    submitCount: state.submitCount + 1
                }))
                setDisabled(true)
            }
        }).catch(({message}) => {
            setSpinning(false)
            form.props.notify({
                message: locale.errorTitle,
                description: message,
            })
        })
    }
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Setting')
    const initialValues = useMemo(() => (pick(userInfo, [
        'firstname', 'lastname', 'avatar', 'email', 'username'
    ])), [])
    const [edited, setEdited] = useState(initialValues)
    const [userImage, setUserImage] = useState(initialValues.avatar);
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
    const avatarElement = useMemo(() => {
        return <Avatar
            style={disabled ? {cursor: 'not-allowed'} : {cursor: 'pointer'}}
            src={userImage}
            size={64} icon={<UserOutlined/>}/>
    }, [userImage, disabled])
    const onReset = useCallback(() => {
        setEdited((edited) => ({...edited, avatar: null}))
        setUserImage(null);
        if (field_errors.avatar)
            setFieldErrors({...field_errors, avatar: undefined})
    }, []);
    const modified = useMemo(() => {
        return !isEqual(edited, initialValues)
    }, [edited, initialValues])
    return <Flex gap="middle" vertical>
        <div key={'controls'}><Segmented
            options={[
                {value: true, icon: <BulbOutlined/>},
                {value: false, icon: <EditOutlined/>},
            ]}
            onChange={(value) => {
                setDisabled(value)
                let values = value ? initialValues : edited;
                _form.setFieldsValue(values)
                setUserImage(values.avatar);
            }}
        /></div>
        <Form
            key={'form'}
            form={_form}
            disabled={disabled}
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
            onFinish={onFinish}>
            <Form.Item
                name="avatar"
                validateStatus={field_errors.avatar ? "error" : undefined}
                help={field_errors.avatar}>
                <Flex gap="middle" align="center">
                    {disabled ? avatarElement :
                        <div {...getRootProps({className: 'dropzone'})}>
                            <input {...getInputProps()} />
                            <label htmlFor='icon-button-file'>
                                {avatarElement}
                            </label>
                        </div>}
                    {disabled ? null :
                        <div {...getRootProps({className: 'dropzone'})}>
                            <input {...getInputProps()} />
                            <label htmlFor='icon-button-file'>
                                <Button type="primary">Upload</Button>
                            </label>
                        </div>}
                    {disabled ? null : <Button onClick={onReset}>Reset</Button>}
                </Flex>
            </Form.Item>
            <Form.Item
                name="firstname"
                validateStatus={field_errors.firstname ? "error" : undefined}
                help={field_errors.firstname}
                rules={[{
                    required: true,
                    message: locale.firstnameRequired
                }]}>
                <Input
                    prefix={<IdcardOutlined className="site-form-item-icon"/>}
                    placeholder={locale.firstnamePlaceholder} onChange={() => {
                    if (field_errors.firstname)
                        setFieldErrors({...field_errors, firstname: undefined})
                }}/>
            </Form.Item>
            <Form.Item
                name="lastname"
                validateStatus={field_errors.lastname ? "error" : undefined}
                help={field_errors.lastname}
                rules={[{
                    required: true,
                    message: locale.lastnameRequired
                }]}>
                <Input
                    prefix={<IdcardOutlined className="site-form-item-icon"/>}
                    placeholder={locale.lastnamePlaceholder} onChange={() => {
                    if (field_errors.lastname)
                        setFieldErrors({...field_errors, lastname: undefined})
                }}/>
            </Form.Item>
            {disabled && userInfo.email ? <Form.Item name="email">
                <Input
                    prefix={<MailOutlined className="site-form-item-icon"/>}/>
            </Form.Item> : null}
            {disabled && userInfo.username ? <Form.Item name="username">
                <Input
                    prefix={<UserOutlined className="site-form-item-icon"/>}/>
            </Form.Item> : null}
            <Form.Item>
                {disabled ? null :
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
    </Flex>
}