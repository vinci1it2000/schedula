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
import post from "../../../../../core/utils/fetch";

export default function RegisterForm(
    {form, urlRegister, setAuth, setSpinning}) {

    const [field_errors, setFieldErrors] = useState({});

    const onFinish = (data) => {
        setSpinning(true)
        post({
            url: urlRegister,
            data,
            form
        }).then(({data, messages}) => {
            setSpinning(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
                if (data.field_errors) {
                    setFieldErrors(data.field_errors || {})
                }
            } else {
                setAuth('login')
            }
        }).catch(error => {
            setSpinning(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
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
        <Form.Item
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
                placeholder={locale.emailPlaceholder} onChange={() => {
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
            <Input
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordPlaceholder}
                onChange={() => {
                    if (field_errors.password)
                        setFieldErrors({
                            ...field_errors,
                            password: undefined
                        })
                }}
            />
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
            <Input
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordConfirmPlaceholder}
                onChange={() => {
                    if (field_errors.password_confirm)
                        setFieldErrors({
                            ...field_errors,
                            password_confirm: undefined
                        })
                }}
            />
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