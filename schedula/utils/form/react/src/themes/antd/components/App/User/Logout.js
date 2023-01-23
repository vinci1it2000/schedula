import {
    Button,
    Form
} from 'antd'
import {useLocaleStore} from "../../../models/locale";
import post from "../../../../../core/utils/fetch";

export default function LogoutForm(
    {form, urlLogout, setOpen,setAuth, setSpinning}) {
    const onFinish = () => {
        setSpinning(true)
        post({
            url: urlLogout,
            data: {},
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
            } else {
                form.setState({
                    ...form.state, userInfo: {},
                    submitCount: form.state.submitCount + 1
                })
                setOpen(false)
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
    const locale = getLocale('User.Logout')
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
        <Form.Item>
            <Button type="primary" htmlType="submit" style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
        </Form.Item>
    </Form>
}