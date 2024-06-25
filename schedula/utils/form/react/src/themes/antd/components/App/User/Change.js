import {
    Button,
    Form,
    Input
} from 'antd'
import {useState} from "react";
import {
    LockOutlined
} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";

export default function ChangePasswordForm(
    {form, urlChangePassword, setAuth, setSpinning, setOpen}) {

    const [field_errors, setFieldErrors] = useState({});

    const onFinish = (data) => {
        setSpinning(true)
        form.postData({
            url: urlChangePassword,
            data,
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
            } else if (response) {
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
        }).catch(({message}) => {
            setSpinning(false)
            form.props.notify({
                message: locale.errorTitle,
                description: message,
            })
        })
    }
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.ChangePassword')
    return <Form
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
            <Input
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
            <Input
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
            <Input
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
    </Form>
}