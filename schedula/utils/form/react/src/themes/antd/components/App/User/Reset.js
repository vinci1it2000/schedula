import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {LockOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ResetPasswordForm(
    {form, urlResetPassword, setOpen, setSpinning, setAuth}) {
    const [field_errors, setFieldErrors] = useState({});
    const {queryInfo: {token = null}} = form.state
    const onFinish = (data) => {
        setSpinning(true)
        form.postData({
            url: `${urlResetPassword}/${token}`,
            data
        }).then(({data: {error, errors, field_errors, response}}) => {
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