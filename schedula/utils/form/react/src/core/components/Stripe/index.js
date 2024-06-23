import {loadStripe} from "@stripe/stripe-js";
import React, {useState, useCallback, useMemo, useEffect} from "react";
import {
    EmbeddedCheckoutProvider,
    EmbeddedCheckout
} from "@stripe/react-stripe-js";
import post from "../../../core/utils/fetch";
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

    const stripe = useMemo(() => {
        const {stripe} = form.state
        if (stripe)
            return stripe;
        return loadStripe(stripeKey).then(stripe => {
            form.setState({...form.state, stripe})
            return stripe
        });
    }, [stripeKey, form]);
    useEffect(() => {
        if (!clientSecret) {
            post({
                url: urlCreateCheckoutSession,
                data: checkoutProps,
                form
            }).then(({data: {error, sessionId, clientSecret}}) => {
                if (error) {
                    form.props.notify({type: 'error', message: error})
                } else {
                    setSessionId(sessionId)
                    setClientSecret(clientSecret)
                }
            })
        }
    }, [])
    const onComplete = useCallback(() => {
        post({
            url: `${urlCreateCheckoutStatus}/${sessionId}`,
            method: 'GET',
            form
        }).then(({data}) => {
            form.setState({...form.state, userInfo: data.userInfo})
            if (onCheckout)
                onCheckout(data)
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