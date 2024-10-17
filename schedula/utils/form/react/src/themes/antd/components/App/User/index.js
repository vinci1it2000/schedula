import {
    Drawer, Tooltip, Button, Spin, Space, Dropdown, Avatar
} from 'antd'
import {
    LoginOutlined,
    LogoutOutlined,
    SettingOutlined,
    UserOutlined,
    LockOutlined,
    BankOutlined
} from "@ant-design/icons";
import React, {useState, useEffect, useMemo, useRef} from "react";
import {useLocaleStore} from "../../../models/locale";
import isEmpty from "lodash/isEmpty";
import {useLocation} from "react-router-dom";

const LoginForm = React.lazy(() => import( "./Login"))
const RegisterForm = React.lazy(() => import( "./Register"))
const ForgotForm = React.lazy(() => import( "./Forgot"))
const ConfirmForm = React.lazy(() => import( "./Confirm"))
const ResetForm = React.lazy(() => import( "./Reset"))
const ChangePasswordForm = React.lazy(() => import( "./Change"))
const InfoForm = React.lazy(() => import( "./Info"))
const SettingsForm = React.lazy(() => import( "./Settings"))
const LogoutForm = React.lazy(() => import( "./Logout"))

const Content = ({isActive, children, style}) => {
    const [hasRendered, setHasRendered] = useState(false);

    if (isActive && !hasRendered) {
        setHasRendered(true);
    }

    return <div style={{
        height: "100%",
        width: "100%", ...style,
        display: isActive ? 'block' : 'none'
    }}>
        {hasRendered && children}
    </div>
};
export default function UserNav(
    {
        id = 'user-nav',
        form,
        loginRequired,
        urlForgotPassword,
        urlChangePassword,
        urlLogin,
        urlRegister,
        registerAddUsername = false,
        registerCustomData = [],
        urlConfirmMail,
        urlResetPassword,
        urlLogout,
        urlEdit,
        urlSettings,
        urlBillingPortal,
        settingProps,
        formContext,
        containerRef
    }) {
    const portalRef = useRef()
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User')
    const StripePortal = useMemo(() => {
        return window.schedula.getComponents({
            render: {formContext}, component: 'Stripe.Portal'
        })
    }, [])

    const {userInfo = {}, emitter} = form.state
    const {pathname, search, hash: anchor} = useLocation()
    const [spinning, setSpinning] = useState(false);
    const [open, setOpen] = useState(false);
    const [auth, setAuth] = useState(null);

    useEffect(() => {
        emitter.on('set-auth', (v) => {
            setAuth(v)
            if (isEmpty(form.state.userInfo) && v === 'login') {
                setOpen(true)
            }
        })
    }, [emitter, form])

    const {logged, titles} = useMemo(() => {
        let logged = !isEmpty(userInfo)
        return {
            logged, titles: logged ? {
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
        }
    }, [userInfo])
    const mustLogin = useMemo(() => {
        return loginRequired === true || (typeof loginRequired === 'object' && loginRequired[pathname])
    }, [pathname, loginRequired])
    useEffect(() => {
        let auth = (anchor || '#').substring(1),
            open = titles.hasOwnProperty(auth);
        auth = (open && auth) || 'login';
        if (mustLogin && !logged) {
            setOpen(true)
            setAuth('login')
        } else {
            setAuth(auth)
            setOpen(open)
        }
    }, [logged, anchor, titles, mustLogin])
    return <div key={id}>
        {logged ? <Dropdown key={'right-menu'} menu={{
            selectedKeys: [], onClick: ({key}) => {
                if (!['billing-portal'].includes(key)) {
                    setAuth(key)
                    setOpen(true)
                }
            }, items: [{
                key: 'info', icon: <UserOutlined/>, label: locale.infoButton
            }, (urlChangePassword ? {
                key: 'change-password',
                icon: <LockOutlined/>,
                label: locale.changePasswordButton
            } : null), (urlBillingPortal ? {
                key: 'billing-portal',
                icon: <BankOutlined/>,
                label: locale.billingPortalButton,
                onClick: () => {
                    portalRef.current.click()
                }
            } : null), (urlSettings ? {
                key: 'settings',
                icon: <SettingOutlined/>,
                label: locale.settingButton
            } : null), {
                type: 'divider'
            }, {
                key: 'logout',
                icon: <LogoutOutlined/>,
                label: locale.logoutButton
            }].filter(v => !!v)
        }}>
            <Space>
                {userInfo.avatar ? <Avatar src={userInfo.avatar}/> : <Button
                    type="primary" shape="circle" icon={<UserOutlined/>}/>}
                {userInfo.username}
                <StripePortal
                    ref={portalRef}
                    key={'billing-portal'}
                    render={{formContext}}
                    width={"80%"}
                    height={"80%"}
                    left={"10%"}
                    bottom={"10%"}
                    urlPortalSession={urlBillingPortal}
                />
            </Space>
        </Dropdown> : <Tooltip
            key={'btn'} title={locale.buttonTooltip}
            placement="bottomRight">
            <Button
                type="primary"
                shape="circle"
                onClick={() => {
                    setAuth('login')
                    setOpen(true)
                }}
                icon={<LoginOutlined/>}
            />
        </Tooltip>}
        <Drawer
            key="Drawer"
            rootStyle={{position: "absolute"}}
            title={titles[auth]}
            closable={!spinning && !(mustLogin && !logged)}
            onClose={() => {
                if (!spinning && !(mustLogin && !logged)) {
                    setOpen(false)
                    if (anchor) {
                        window.history.pushState({}, "", pathname + search);
                    }
                    setAuth(null)
                }
            }}
            getContainer={() => {
                return containerRef.current
            }}
            open={open}>
            <Spin key={'page'} spinning={spinning}>
                <Content key='register' isActive={auth === 'register'}>
                    <RegisterForm
                        form={form}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}
                        addUsername={registerAddUsername}
                        customData={registerCustomData}
                    />
                </Content>
                <Content key='confirm' isActive={auth === 'confirm'}>
                    <ConfirmForm
                        form={form}
                        urlConfirmMail={urlConfirmMail}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/>
                </Content>
                <Content key='login' isActive={auth === 'login'}>
                    <LoginForm
                        form={form}
                        urlLogin={urlLogin}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/>
                </Content>
                <Content key='forgot' isActive={auth === 'forgot'}>
                    <ForgotForm
                        form={form}
                        urlForgotPassword={urlForgotPassword}
                        setAuth={setAuth}
                        setSpinning={setSpinning}/>
                </Content>
                <Content key='reset' isActive={auth === 'reset'}>
                    <ResetForm
                        form={form}
                        urlResetPassword={urlResetPassword}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/>
                </Content>
                <Content key='change-password'
                         isActive={auth === 'change-password'}>
                    <ChangePasswordForm
                        form={form}
                        urlChangePassword={urlChangePassword}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/>
                </Content>
                <Content key='logout' isActive={auth === 'logout'}>
                    <LogoutForm
                        form={form}
                        urlLogout={urlLogout}
                        setSpinning={setSpinning}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='info' isActive={auth === 'info'}>
                    <InfoForm
                        form={form}
                        userInfo={userInfo}
                        urlEdit={urlEdit}
                        setSpinning={setSpinning}
                        addUsername={registerAddUsername}
                        customData={registerCustomData}
                    />
                </Content>
                <Content key='settings' isActive={auth === 'settings'}>
                    <SettingsForm
                        formContext={formContext}
                        userInfo={userInfo}
                        urlSettings={urlSettings}
                        setAuth={setAuth}
                        setSpinning={setSpinning}
                        {...settingProps}
                    />
                </Content>
            </Spin>
        </Drawer>
    </div>
}