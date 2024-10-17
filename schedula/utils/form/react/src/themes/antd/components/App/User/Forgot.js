import {
    Button,
    Form,
    Input,
    Spin
} from 'antd'
import {useState, useCallback} from "react";
import {MailOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ForgotForm(
    {form, urlForgotPassword, setAuth}) {
    const [spinning, setSpinning] = useState(false);
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = useCallback((data) => {
        setSpinning(true)
        form.postData({
            url: urlForgotPassword,
            data
        }, () => {
            setSpinning(false)
            setAuth('login')
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlForgotPassword, setAuth])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Forgot')
    return <Spin spinning={spinning}><Form
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
    </Form></Spin>
}