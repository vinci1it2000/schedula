import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {
    MailOutlined,
    LockOutlined,
    UserOutlined,
    IdcardOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function RegisterForm(
    {form, urlRegister, setAuth, setSpinning, setOpen, addUsername = false}) {

    const [field_errors, setFieldErrors] = useState({});

    const onFinish = (data) => {
        setSpinning(true)
        form.postData({
            url: urlRegister,
            data
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
    }
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Register')
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
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