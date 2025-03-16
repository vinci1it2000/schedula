import {
    Button,
    Form,
    Checkbox,
    Input,
    Spin
} from 'antd'
import {useState, useCallback} from "react";
import {MailOutlined, LockOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function LoginForm(
    {
        render: {formContext: {form}},
        urlLogin,
        urlRegister,
        setAuth,
        setOpen,
        ...props
    }) {
    const [spinning, setSpinning] = useState(false);
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = useCallback(({email, password, remember}) => {
        setSpinning(true)
        form.postData({
            url: urlLogin,
            data: {email, password, remember},
        }, ({data: {response}}) => {
            setSpinning(false)
            const {user = {}} = response
            form.setState((state) => ({
                ...state,
                userInfo: {email, ...user},
                submitCount: state.submitCount + 1
            }))
            setOpen(false)
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlLogin])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Login')
    return <Spin wrapperClassName={"full-height-spin"} spinning={spinning}><Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        initialValues={{remember: true}}
        onFinish={onFinish}
        {...props}>
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
            style={{marginBottom: 0}}
            name="password"
            validateStatus={field_errors.password ? "error" : undefined}
            help={field_errors.password}
            rules={[{
                required: true,
                message: locale.passwordRequired
            }]}>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordPlaceholder}
                autoComplete="current-password"
                onChange={() => {
                    if (field_errors.password)
                        setFieldErrors({
                            ...field_errors,
                            password: undefined
                        })
                }}
            />
        </Form.Item>
        <Form.Item>
            <Form.Item
                validateStatus={field_errors.remember ? "error" : undefined}
                help={field_errors.remember}
                name="remember" valuePropName="checked" noStyle>
                <Checkbox onChange={() => {
                    if (field_errors.remember)
                        setFieldErrors({
                            ...field_errors,
                            remember: undefined
                        })
                }}>{locale.rememberMe}</Checkbox>
            </Form.Item>
            <a href="#forgot" style={{float: 'right'}} onClick={() => {
                setAuth('forgot')
            }}>
                {locale.forgotPassword}
            </a>
        </Form.Item>
        <Form.Item>
            <Button type="primary" htmlType="submit"
                    style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
            {urlRegister ? <>{locale.or} <a href="#register" onClick={() => {
                setAuth('register')
            }}>{locale.registerNow}</a></> : null}
            <br/>
            <>{locale.or} <a href="#confirm" onClick={() => {
                setAuth('confirm')
            }}>
                {locale.sendConfirmMail}</a></>
        </Form.Item>
    </Form></Spin>
}