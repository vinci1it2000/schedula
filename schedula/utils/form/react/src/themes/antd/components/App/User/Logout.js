import {
    Button,
    Form,
    Spin
} from 'antd'
import {useLocaleStore} from "../../../models/locale";
import {useCallback, useState} from "react";

export default function LogoutForm(
    {render: {formContext: {form}}, urlLogout, setOpen, setAuth}) {
    const [spinning, setSpinning] = useState(false);
    const onFinish = useCallback(() => {
        setSpinning(true)
        form.postData({
            url: urlLogout,
        }, () => {
            setSpinning(false)
            form.setState((state) => ({
                ...state, userInfo: {},
                submitCount: state.submitCount + 1
            }))
            setOpen(false)
            setAuth('login')
        }, () => {
            setSpinning(false)
        })
    }, [form, urlLogout, setOpen, setAuth])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Logout')
    return <Spin wrapperClassName={"full-height-spin"} spinning={spinning}><Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
        <Form.Item>
            <Button type="primary" htmlType="submit" style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
        </Form.Item>
    </Form></Spin>
}