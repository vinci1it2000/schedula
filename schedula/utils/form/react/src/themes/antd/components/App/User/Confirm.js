import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {MailOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import post from "../../../../../core/utils/fetch";

export default function ConfirmForm(
    {form, urlConfirmMail, setAuth, setSpinning}) {
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = ({email}) => {
        setSpinning(true)
        post({
            url: urlConfirmMail,
            data: {email},
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
    const locale = getLocale('User.Confirm')
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
                placeholder={locale.emailPlaceholder} onChange={() => {
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