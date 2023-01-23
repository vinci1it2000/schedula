import {
    Button,
    Form,
    Input
} from 'antd'
import {useState, createRef, useEffect} from "react";
import ReCAPTCHA from "react-google-recaptcha";
import {MailOutlined, UserOutlined, TagOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import post from "../../../../../core/utils/fetch";

export default function ContactForm(
    {form, formContext, urlContact, setSpinning}) {
    const {reCAPTCHA} = formContext
    const {userInfo = {}} = form.state
    const [_form] = Form.useForm();
    useEffect(() => {
        _form.setFieldsValue({
            name: ((userInfo.firstname || '') + ' ' + (userInfo.lastname || '')).trim(),
            email: userInfo.email
        })
    }, [_form, userInfo])
    const recaptchaRef = createRef();
    const [field_errors, setFieldErrors] = useState({});
    const onFinish = ({name, email, subject, message}) => {
        setSpinning(true)
        const recaptcha = recaptchaRef.current.getValue();
        post({
            url: urlContact,
            data: {
                name,
                email,
                subject,
                message,
                'g-recaptcha-response': recaptcha
            },
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
    const locale = getLocale('Contact')
    return <Form
        form={_form}
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
        <Form.Item
            rules={[{required: true, message: locale.nameRequired}]}
            name="name">
            <Input
                prefix={<UserOutlined className="site-form-item-icon"/>}
                placeholder={locale.namePlaceholder}/>
        </Form.Item>
        <Form.Item
            name="email"
            validateStatus={field_errors.email ? "error" : undefined}
            help={field_errors.email}
            rules={[
                {required: true, message: locale.emailRequired},
                {type: 'email', message: locale.emailInvalid}
            ]}>
            <Input
                prefix={<MailOutlined className="site-form-item-icon"/>}
                placeholder={locale.emailPlaceholder} onChange={() => {
                if (field_errors.email)
                    setFieldErrors({...field_errors, email: undefined})
            }}/>
        </Form.Item>
        <Form.Item
            rules={[{required: true, message: locale.subjectRequired}]}
            name="subject">
            <Input
                prefix={<TagOutlined className="site-form-item-icon"/>}
                placeholder={locale.subjectPlaceholder}/>
        </Form.Item>
        <Form.Item
            rules={[{required: true, message: locale.messageRequired}]}
            name="message">
            <Input.TextArea placeholder={locale.messagePlaceholder} rows={5}/>
        </Form.Item>
        {reCAPTCHA ? <Form.Item
            rules={[{required: true, message: locale.messageRequired}]}
            name="recaptcha">
            <ReCAPTCHA
                ref={recaptchaRef}
                sitekey={reCAPTCHA}
                hl={form.state.language.replace('_', '-')}/>
        </Form.Item> : null}
        <Form.Item>
            <Button type="primary" htmlType="submit" style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
        </Form.Item>
    </Form>
}