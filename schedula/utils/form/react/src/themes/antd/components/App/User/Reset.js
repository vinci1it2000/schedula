import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {LockOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import {useQueryStore} from "../../../models/query";
import post from "../../../../../core/utils/fetch";

export default function ResetPasswordForm(
    {form, urlResetPassword, setOpen, setSpinning, setAuth}) {
    const [field_errors, setFieldErrors] = useState({});
    const {query: {token = null}} = useQueryStore()
    const onFinish = (data) => {
        setSpinning(true)
        post({
            url: `${urlResetPassword}/${token}`,
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
                const {response = {}} = data
                const {user = {}} = response
                form.setState({
                    ...form.state,
                    userInfo: user,
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
    const locale = getLocale('User.ResetPassword')
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
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
                autoComplete="new-password" onChange={() => {
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
                autoComplete="new-password" onChange={() => {
                    if (field_errors.password_confirm)
                        setFieldErrors({
                            ...field_errors,
                            password_confirm: undefined
                        })
                }}
            />
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