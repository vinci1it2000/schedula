import {
    Button,
    Form,
    Input,
    Spin
} from 'antd'
import {useCallback, useState} from "react";
import {MailOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ConfirmForm(
    {render: {formContext: {form}}, urlConfirmMail, setAuth, setOpen}
) {
    const [spinning, setSpinning] = useState(false);
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = useCallback(({email}) => {
        setSpinning(true)
        form.postData({
            url: urlConfirmMail,
            data: {email},
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
                setOpen(false);
            } else {
                setAuth('login')
            }
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlConfirmMail, setAuth, setOpen])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Confirm')
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
    </Form></Spin>
}