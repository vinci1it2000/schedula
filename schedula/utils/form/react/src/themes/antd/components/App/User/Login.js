import {
    Button,
    Form,
    Checkbox,
    Input
} from 'antd'
import {useState} from "react";
import {MailOutlined, LockOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import post from "../../../../../core/utils/fetch";

export default function LoginForm(
    {
        form,
        urlLogin,
        urlRegister,
        setAuth,
        setOpen,
        setSpinning,
        ...props
    }) {
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = ({email, password, remember}) => {
        setSpinning(true)
        post({
            url: urlLogin,
            data: {email, password, remember},
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
                const {response = {}} = data
                const {user = {}} = response
                form.setState({
                    ...form.state,
                    userInfo: {email, ...user},
                    submitCount: form.state.submitCount + 1
                })
                setOpen(false)
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
    const locale = getLocale('User.Login')
    return <Form
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
                placeholder={locale.emailPlaceholder} onChange={() => {
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
    </Form>
}