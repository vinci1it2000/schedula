import {
    Avatar,
    Button,
    Flex,
    Form,
    Input
} from 'antd'
import {useCallback, useState} from "react";
import {
    MailOutlined,
    LockOutlined,
    UserOutlined,
    IdcardOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import pick from 'lodash/pick';
import omit from "lodash/omit";
import {useDropzone} from "react-dropzone";

export default function RegisterForm(
    {
        form,
        urlRegister,
        setAuth,
        setSpinning,
        setOpen,
        customData,
        addUsername = false
    }) {

    const [field_errors, setFieldErrors] = useState({});
    const onFinish = useCallback((data) => {
        setSpinning(true)
        const customDataKeys = (customData || []).map(({name}) => name)
        const newData = omit(data, customDataKeys);
        newData.custom_data = pick(data, customDataKeys)
        form.postData({
            url: urlRegister,
            data: newData
        }, ({data: {response}}) => {
            setSpinning(false)
            if (response) {
                const {user = {}} = response
                form.setState((state) => ({
                    ...state,
                    userInfo: user,
                    submitCount: state.submitCount + 1
                }))
                const {protocol, host, pathname, search} = window.location;
                const newUrl = `${protocol}//${host}${pathname}${search}`;
                window.history.replaceState(null, '', newUrl);
                setOpen(false)
            } else {
                setAuth('login')
            }
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlRegister, setAuth, setSpinning, setOpen, customData])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Register')
    const [userImage, setUserImage] = useState();
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
                    if (field_errors.avatar)
                        setFieldErrors({...field_errors, avatar: undefined})
                };
                reader.readAsDataURL(acceptedFiles[0]);
            }
        }
    });
    const onReset = useCallback(() => {
        setUserImage(null);
        if (field_errors.avatar)
            setFieldErrors({...field_errors, avatar: undefined})
    }, []);
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={(data) => onFinish({avatar: userImage, ...data})}>
        <Form.Item
            name="avatar"
            validateStatus={field_errors.avatar ? "error" : undefined}
            help={field_errors.avatar}>
            <Flex gap="middle" align="center">
                <div {...getRootProps({className: 'dropzone'})}>
                    <input {...getInputProps()} />
                    <label htmlFor='icon-button-file'>
                        <Avatar
                            style={{cursor: 'pointer'}}
                            src={userImage}
                            size={64} icon={<UserOutlined/>}/>
                    </label>
                </div>
                <div {...getRootProps({className: 'dropzone'})}>
                    <input {...getInputProps()} />
                    <label htmlFor='icon-button-file'>
                        <Button type="primary">{locale.avatarUpload}</Button>
                    </label>
                </div>
                <Button onClick={onReset}>{locale.avatarReset}</Button>
            </Flex>
        </Form.Item>
        <Form.Item
            name="email"
            validateStatus={field_errors.email ? "error" : undefined}
            help={field_errors.email}
            rules={[{
                required: true,
                message: locale.emailRequired
            }, {
                type: 'email',
                message: locale.emailInvalid
            }]}>
            <Input
                prefix={<MailOutlined className="site-form-item-icon"/>}
                placeholder={locale.emailPlaceholder} autoComplete="username"
                onChange={() => {
                    if (field_errors.email)
                        setFieldErrors({...field_errors, email: undefined})
                }}/>
        </Form.Item>
        {addUsername ? <Form.Item
            name="username"
            validateStatus={field_errors.username ? "error" : undefined}
            help={field_errors.username}
            rules={[{
                required: true,
                message: locale.usernameRequired
            }]}>
            <Input
                prefix={<UserOutlined className="site-form-item-icon"/>}
                placeholder={locale.usernamePlaceholder} onChange={() => {
                if (field_errors.username)
                    setFieldErrors({...field_errors, username: undefined})
            }}/>
        </Form.Item> : null}
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
        {(customData || []).map(({name, itemProps, inputProps}) => <Form.Item
            name={name}
            validateStatus={field_errors[name] ? "error" : undefined}
            help={field_errors[name]}
            {...itemProps}>
            <Input {...inputProps} onChange={() => {
                if (field_errors[name])
                    setFieldErrors({...field_errors, [name]: undefined})
            }}/>
        </Form.Item>)}
        <Form.Item
            name="password"
            validateStatus={field_errors.password ? "error" : undefined}
            help={field_errors.password}
            rules={[{
                required: true,
                message: locale.passwordRequired
            }]} hasFeedback>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordPlaceholder}
                autoComplete="new-password" onChange={() => {
                if (field_errors.password)
                    setFieldErrors({
                        ...field_errors,
                        password: undefined
                    })
            }}/>
        </Form.Item>
        <Form.Item
            name="password_confirm"
            dependencies={['password']}
            hasFeedback
            rules={[
                {
                    required: true,
                    message: locale.passwordConfirmRequired,
                },
                ({getFieldValue}) => ({
                    validator(_, value) {
                        if (!value || getFieldValue('password') === value) {
                            return Promise.resolve();
                        }
                        return Promise.reject(new Error(locale.passwordConfirmError));
                    },
                }),
            ]}>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordConfirmPlaceholder}
                autoComplete="new-password" onChange={() => {
                if (field_errors.password_confirm)
                    setFieldErrors({
                        ...field_errors,
                        password_confirm: undefined
                    })
            }}/>
        </Form.Item>
        <Form.Item>
            <Button type="primary" htmlType="submit"
                    style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
            {locale.or}
            <a href="#login" onClick={() => {
                setAuth('login')
            }}> {locale.login}</a>
        </Form.Item>
    </Form>
}