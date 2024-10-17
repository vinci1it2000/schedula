import {
    Button,
    Form,
    Input,
    Spin
} from 'antd'
import {useState, useCallback} from "react";
import {
    LockOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ChangePasswordForm(
    {form, urlChangePassword, setAuth, setOpen}) {
    const [spinning, setSpinning] = useState(false);
    const [field_errors, setFieldErrors] = useState({});

    const onFinish = useCallback((data) => {
        setSpinning(true)
        form.postData({
            url: urlChangePassword,
            data,
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
                setOpen(false)
            } else {
                setAuth('login')
            }
        }, ({data: {field_errors}}) => {
            setSpinning(false)
            if (field_errors) {
                setFieldErrors(field_errors || {})
            }
        })
    }, [form, urlChangePassword, setAuth, setOpen])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.ChangePassword')
    return <Spin spinning={spinning}><Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
        <Form.Item
            name="password"
            validateStatus={field_errors.password ? "error" : undefined}
            help={field_errors.password}
            rules={[{
                required: true,
                message: locale.currentPasswordRequired
            }]} hasFeedback>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.currentPasswordPlaceholder}
                autoComplete="current-password" onChange={() => {
                if (field_errors.password)
                    setFieldErrors({
                        ...field_errors,
                        password: undefined
                    })
            }}/>
        </Form.Item>
        <Form.Item
            name="new_password"
            validateStatus={field_errors.new_password ? "error" : undefined}
            help={field_errors.new_password}
            rules={[{
                required: true,
                message: locale.passwordRequired
            }]} hasFeedback>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordPlaceholder}
                autoComplete="new-password" onChange={() => {
                if (field_errors.new_password)
                    setFieldErrors({
                        ...field_errors,
                        new_password: undefined
                    })
            }}/>
        </Form.Item>
        <Form.Item
            name="new_password_confirm"
            dependencies={['new_password']}
            hasFeedback
            rules={[
                {
                    required: true,
                    message: locale.passwordConfirmRequired,
                },
                ({getFieldValue}) => ({
                    validator(_, value) {
                        if (!value || getFieldValue('new_password') === value) {
                            return Promise.resolve();
                        }
                        return Promise.reject(new Error(locale.passwordConfirmError));
                    },
                }),
            ]}>
            <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                type="password" placeholder={locale.passwordConfirmPlaceholder}
                autoComplete="new-password" onChange={() => {
                if (field_errors.new_password_confirm)
                    setFieldErrors({
                        ...field_errors,
                        new_password_confirm: undefined
                    })
            }}/>
        </Form.Item>
        <Form.Item>
            <Button type="primary" htmlType="submit"
                    style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
        </Form.Item>
    </Form></Spin>
}