import {
    Drawer,
    Tooltip,
    Button,
    Spin,
    Space,
    Dropdown
} from 'antd'
import {
    LoginOutlined,
    LogoutOutlined,
    SettingOutlined,
    UserOutlined
} from "@ant-design/icons";
import React, {useState, Suspense, useEffect} from "react";
import {useLocaleStore} from "../../../models/locale";
import isEmpty from "lodash/isEmpty";

const LoginForm = React.lazy(() => import( "./Login"))
const RegisterForm = React.lazy(() => import( "./Register"))
const ForgotForm = React.lazy(() => import( "./Forgot"))
const ConfirmForm = React.lazy(() => import( "./Confirm"))
const ResetForm = React.lazy(() => import( "./Reset"))
const InfoForm = React.lazy(() => import( "./Info"))
const SettingForm = React.lazy(() => import( "./Setting"))
const LogoutForm = React.lazy(() => import( "./Logout"))

export default function UserNav(
    {
        key = 'user-nav',
        form,
        loginRequired,
        urlForgotPassword,
        urlLogin,
        urlRegister,
        urlConfirmMail,
        urlResetPassword,
        urlLogout,
        urlSettings,
        containerRef
    }) {
    const {userInfo = {}} = form.state
    const logged = !isEmpty(userInfo)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User')

    const titles = logged ? {
        info: locale.titleInfo,
        setting: locale.titleSetting,
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
                    key: 'setting',
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
                <Button
                    type="primary" shape="circle"
                    icon={<UserOutlined/>}/>
                {userInfo.username}
            </Space>
        </Dropdown> : <Tooltip
            key={'btn'} title={locale.buttonTooltip} placement="bottomRight">
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
            getContainer={containerRef.current}
            open={open}>
            <Spin key={'page'} spinning={spinning}>
                <Suspense>
                {auth === 'login' ?
                    <LoginForm
                        key={'login'}
                        form={form}
                        urlLogin={urlLogin}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/> : null}
                {auth === 'register' ?
                    <RegisterForm
                        key={'register'}
                        form={form}
                        urlLogin={urlLogin}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/> : null}
                {auth === 'forgot' ?
                    <ForgotForm
                        key={'forgot'}
                        form={form}
                        urlForgotPassword={urlForgotPassword}
                        setAuth={setAuth}
                        setSpinning={setSpinning}/> : null}
                {auth === 'confirm' ?
                    <ConfirmForm
                        key={'confirm'}
                        form={form}
                        urlConfirmMail={urlConfirmMail}
                        setAuth={setAuth}
                        setSpinning={setSpinning}/> : null}
                {auth === 'reset' ?
                    <ResetForm
                        key={'reset'}
                        form={form}
                        urlResetPassword={urlResetPassword}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/> : null}
                {auth === 'info' ?
                    <InfoForm
                        key={'info'}
                        userInfo={userInfo}
                        form={form}
                        setAuth={setAuth}
                        setSpinning={setSpinning}/> : null}
                {auth === 'setting' ?
                    <SettingForm
                        key={'setting'}
                        form={form}
                        userInfo={userInfo}
                        urlSettings={urlSettings}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/> : null}
                {auth === 'logout' ?
                    <LogoutForm
                        key={'logout'}
                        form={form}
                        urlLogout={urlLogout}
                        setSpinning={setSpinning}
                        setAuth={setAuth}
                        setOpen={setOpen}/> : null}
                </Suspense>
            </Spin>
        </Drawer>
    </div>
}