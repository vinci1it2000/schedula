import {
    Drawer, Tooltip, Button, Space, Dropdown, Avatar, Skeleton
} from 'antd'
import {
    LoginOutlined,
    LogoutOutlined,
    SettingOutlined,
    UserOutlined,
    LockOutlined,
    BankOutlined
} from "@ant-design/icons";
import React, {useState, useEffect, useMemo, useRef, Suspense} from "react";
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
const getContainerElement = (refContainer) => {
    if (refContainer === null) {
        return null; // Return null if refContainer is null
    } else if (typeof refContainer === 'string') {
        return document.querySelector(refContainer); // Use the string selector
    } else if (refContainer && refContainer.current) {
        return refContainer.current; // Use the ref
    }
    return null; // Fallback if none of the conditions match
};
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
        render,
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
        containerRef
    }) {
    const {formContext: {form}} = render
    const portalRef = useRef()
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User')
    const StripePortal = useMemo(() => {
        return window.schedula.getComponents({
            render, component: 'Stripe.Portal'
        })
    }, [render])

    const {userInfo = {}, emitter} = form.state
    const {pathname, search, hash: anchor} = useLocation()
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
                    render={render}
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
            autoFocus={false}
            forceRender={true}
            rootStyle={{position: "absolute"}}
            title={titles[auth]}
            closable={!(mustLogin && !logged)}
            onClose={() => {
                if (!(mustLogin && !logged)) {
                    setOpen(false)
                    if (anchor) {
                        window.history.pushState({}, "", pathname + search);
                    }
                    setAuth(null)
                }
            }}
            getContainer={() => getContainerElement(containerRef)}
            open={open}>
            <Suspense fallback={<Skeleton/>}>
                <Content key='register' isActive={auth === 'register'}>
                    <RegisterForm
                        render={render}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setOpen={setOpen}
                        addUsername={registerAddUsername}
                        customData={registerCustomData}
                    />
                </Content>
                <Content key='confirm' isActive={auth === 'confirm'}>
                    <ConfirmForm
                        render={render}
                        urlConfirmMail={urlConfirmMail}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='login' isActive={auth === 'login'}>
                    <LoginForm
                        render={render}
                        urlLogin={urlLogin}
                        urlRegister={urlRegister}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='forgot' isActive={auth === 'forgot'}>
                    <ForgotForm
                        render={render}
                        urlForgotPassword={urlForgotPassword}
                        setAuth={setAuth}
                    />
                </Content>
                <Content key='reset' isActive={auth === 'reset'}>
                    <ResetForm
                        render={render}
                        urlResetPassword={urlResetPassword}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='change-password'
                         isActive={auth === 'change-password'}>
                    <ChangePasswordForm
                        render={render}
                        urlChangePassword={urlChangePassword}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='logout' isActive={auth === 'logout'}>
                    <LogoutForm
                        render={render}
                        urlLogout={urlLogout}
                        setAuth={setAuth}
                        setOpen={setOpen}/>
                </Content>
                <Content key='info' isActive={auth === 'info'}>
                    <InfoForm
                        render={render}
                        urlEdit={urlEdit}
                        addUsername={registerAddUsername}
                        customData={registerCustomData}
                    />
                </Content>
                <Content key='settings' isActive={auth === 'settings'}>
                    <SettingsForm
                        render={render}
                        urlSettings={urlSettings}
                        setAuth={setAuth}
                        {...settingProps}
                    />
                </Content>
            </Suspense>
        </Drawer>
    </div>
}