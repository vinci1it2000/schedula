import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {MailOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ForgotForm(
    {form, urlForgotPassword, setAuth, setSpinning}) {
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = (data) => {
        setSpinning(true)
        form.postData({
            url: urlForgotPassword,
            data
        }).then(({data: {error, errors, field_errors}}) => {
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
                setAuth('login')
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
    const locale = getLocale('User.Forgot')
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
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
        <Form.Item>
            <Button type="primary" htmlType="submit" style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
            <div style={{width: '100%'}}>
                {locale.or} <a href="#login" onClick={() => {
                setAuth('login')
            }}>{locale.login}</a>
            </div>
        </Form.Item>
    </Form>
}