import {loadStripe} from "@stripe/stripe-js";
import React, {useState, useCallback, useMemo, useEffect} from "react";
import {
    EmbeddedCheckoutProvider, EmbeddedCheckout
} from "@stripe/react-stripe-js";
import {getTemplate, getUiOptions} from "@rjsf/utils";

export default function Stripe(
    {
        children,
        render: {formContext: {form, stripeKey}, uiSchema, registry},
        urlCreateCheckoutSession = "/stripe/create-checkout-session",
        urlCreateCheckoutStatus = "/stripe/session-status",
        checkoutProps,
        options: {
            clientSecret: clientSecret_ = undefined,
            sessionId: sessionId_ = undefined,
            ...options
        } = {},
        onCheckout,
        ...props
    }) {
    const uiOptions = getUiOptions(uiSchema);
    const Skeleton = getTemplate('Skeleton', registry, uiOptions);
    const [clientSecret, setClientSecret] = useState(clientSecret_);
    const [sessionId, setSessionId] = useState(sessionId_);
    const {state: {language}} = form
    const stripe = useMemo(() => {
        const {stripe} = form.state
        if (stripe) return stripe;
        return loadStripe(stripeKey).then(stripe => {
            form.setState((state) => ({...state, stripe}))
            return stripe
        });
    }, [stripeKey, form]);
    useEffect(() => {
        if (!clientSecret) {
            form.postData({
                url: urlCreateCheckoutSession,
                data: {locale: language.replace('_', '-').split('-')[0], ...checkoutProps}
            }, ({
                    data: {sessionId, clientSecret, session_url, subscription}
                }) => {
                if (session_url) {
                    window.location.href = session_url
                } else {
                    setSessionId(sessionId)
                    setClientSecret(clientSecret)
                }
            })
        }
    }, [language])
    const onComplete = useCallback(() => {
        form.postData({
            url: `${urlCreateCheckoutStatus}/${sessionId}`, method: 'GET'
        }, ({data}) => {
            form.setState((state) => ({...state, userInfo: data.userInfo}))
            if (onCheckout) onCheckout(data)
        });
    }, [form, onCheckout, urlCreateCheckoutStatus, sessionId]);
    return <Skeleton key="stripe" loading={!clientSecret}>
        <EmbeddedCheckoutProvider
            stripe={stripe}
            options={{onComplete, clientSecret, ...options}}
            {...props}>
            {children ? children : <EmbeddedCheckout/>}
        </EmbeddedCheckoutProvider>
    </Skeleton>
};