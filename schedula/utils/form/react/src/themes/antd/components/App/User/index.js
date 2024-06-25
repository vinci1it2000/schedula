import {
    Drawer,
    Tooltip,
    Button,
    Spin,
    Space,
    Dropdown,
    Avatar,
    Skeleton
} from 'antd'
import {
    LoginOutlined,
    LogoutOutlined,
    SettingOutlined,
    UserOutlined,
    LockOutlined
} from "@ant-design/icons";
import React, {useState, useEffect, useMemo, Suspense} from "react";
import {useLocaleStore} from "../../../models/locale";
import isEmpty from "lodash/isEmpty";

const LoginForm = React.lazy(() => import( "./Login"))
const RegisterForm = React.lazy(() => import( "./Register"))
const ForgotForm = React.lazy(() => import( "./Forgot"))
const ConfirmForm = React.lazy(() => import( "./Confirm"))
const ResetForm = React.lazy(() => import( "./Reset"))
const ChangePasswordForm = React.lazy(() => import( "./Change"))
const InfoForm = React.lazy(() => import( "./Info"))
const SettingsForm = React.lazy(() => import( "./Settings"))
const LogoutForm = React.lazy(() => import( "./Logout"))

export default function UserNav(
    {
        key = 'user-nav',
        form,
        loginRequired,
        urlForgotPassword,
        urlChangePassword,
        urlLogin,
        urlRegister,
        urlConfirmMail,
        urlResetPassword,
        urlLogout,
        urlEdit,
        urlSettings,
        settingProps,
        formContext,
        containerRef
    }) {
    const {userInfo = {}} = form.state
    const logged = !isEmpty(userInfo)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User')

    const titles = logged ? {
        info: locale.titleInfo,
        'change-password': locale.titleChangePassword,
        settings: locale.titleSetting,
        logout: locale.titleLogout,
    } : {
        login: locale.titleLogin,
        forgot: locale.titleForgot,
        register: locale.titleRegister,
        confirm: locale.titleConfirm,
        reset: locale.titleResetPassword
    }
    const page = window.location.hash.slice(1)
    const [spinning, setSpinning] = useState(false);
    const [open, setOpen] = useState(titles.hasOwnProperty(page));
    const [auth, setAuth] = useState((open && page) || 'login');
    useEffect(() => {
        if (loginRequired && !logged) {
            setOpen(true)
            if (!auth) {
                setAuth('login')
            }
        }
    }, [logged, loginRequired])
    const drawerContent = useMemo(() => {
        if (!open) {
            return null
        }
        switch (auth) {
            case 'register':
                return <RegisterForm
                    key={auth}
                    form={form}
                    urlRegister={urlRegister}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    setOpen={setOpen}/>
            case 'confirm':
                return <ConfirmForm
                    key={auth}
                    form={form}
                    urlConfirmMail={urlConfirmMail}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    setOpen={setOpen}/>
            case 'login':
                return <LoginForm
                    key={auth}
                    form={form}
                    urlLogin={urlLogin}
                    urlRegister={urlRegister}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    setOpen={setOpen}/>
            case 'forgot':
                return <ForgotForm
                    key={auth}
                    form={form}
                    urlForgotPassword={urlForgotPassword}
                    setAuth={setAuth}
                    setSpinning={setSpinning}/>
            case 'reset':
                return <ResetForm
                    key={auth}
                    form={form}
                    urlResetPassword={urlResetPassword}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    setOpen={setOpen}/>
            case 'change-password':
                return <ChangePasswordForm
                    key={auth}
                    form={form}
                    urlResetPassword={urlChangePassword}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    setOpen={setOpen}/>
            case 'logout':
                return <LogoutForm
                    key={auth}
                    form={form}
                    urlLogout={urlLogout}
                    setSpinning={setSpinning}
                    setAuth={setAuth}
                    setOpen={setOpen}/>
            case 'info':
                return <InfoForm
                    key={auth}
                    form={form}
                    userInfo={userInfo}
                    urlEdit={urlEdit}
                    setSpinning={setSpinning}/>
            case 'settings':
                return <SettingsForm
                    key={auth}
                    formContext={formContext}
                    userInfo={userInfo}
                    urlSettings={urlSettings}
                    setAuth={setAuth}
                    setSpinning={setSpinning}
                    {...settingProps}
                />
            default:
                return null
        }
    }, [auth, userInfo, open]);
    return <div key={key}>
        {logged ? <Dropdown key={'right-menu'} menu={{
            selectedKeys: [],
            onClick: ({key}) => {
                setAuth(key)
                setOpen(true)
            },
            items: [
                {
                    key: 'info',
                    icon: <UserOutlined/>,
                    label: locale.infoButton
                },
                {
                    key: 'change-password',
                    icon: <LockOutlined/>,
                    label: locale.changePasswordButton
                },
                {
                    key: 'settings',
                    icon: <SettingOutlined/>,
                    label: locale.settingButton
                },
                {
                    type: 'divider'
                },
                {
                    key: 'logout',
                    icon: <LogoutOutlined/>,
                    label: locale.logoutButton
                }
            ]
        }}>
            <Space>
                {userInfo.avatar ?
                    <Avatar src={userInfo.avatar}/>
                    :
                    <Button
                        type="primary" shape="circle" icon={<UserOutlined/>}/>
                }
                {userInfo.username}
            </Space>
        </Dropdown> : <Tooltip
            key={'btn'} title={locale.buttonTooltip}
            placement="bottomRight">
            <Button
                type="primary"
                shape="circle"
                onClick={() => {
                    setOpen(true)
                }}
                icon={<LoginOutlined/>}
            />
        </Tooltip>}
        <Drawer
            rootStyle={{position: "absolute"}}
            title={titles[auth]}
            closable={!spinning && !(loginRequired && !logged)}
            onClose={() => {
                if (!spinning && !(loginRequired && !logged))
                    setOpen(false)
            }}
            getContainer={() => {
                return containerRef.current
            }}
            open={open}>
            <Spin key={'page'} spinning={spinning}>
                <Suspense fallback={<Skeleton/>}>
                    {open && drawerContent}
                </Suspense>
            </Spin>
        </Drawer>
    </div>
}