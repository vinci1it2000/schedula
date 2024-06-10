import {loadStripe} from "@stripe/stripe-js";
import React, {useState, useCallback, useMemo} from "react";
import {
    EmbeddedCheckoutProvider,
    EmbeddedCheckout
} from "@stripe/react-stripe-js";
import post from "../../../core/utils/fetch";

export default function Stripe(
    {
        children,
        render,
        urlCreateCheckoutSession = "/stripe/create-checkout-session",
        urlCreateCheckoutStatus = "/stripe/session-status",
        checkoutProps,
        options,
        onCheckout,
        ...props
    }) {

    const [sessionId, setSessionId] = useState('');
    const {form, stripeKey} = render.formContext

    const stripe = useMemo(() => {
        const {stripe} = form.state
        if (stripe)
            return stripe;
        return loadStripe(stripeKey).then(stripe => {
            form.setState({...form.state, stripe})
            return stripe
        });
    }, [stripeKey, form]);
    const fetchClientSecret = useCallback(() => {
        // Create a Checkout Session
        return post({
            url: urlCreateCheckoutSession,
            data: checkoutProps,
            form
        }).then(({data}) => {
            if (data.error) {
                form.props.notify({type: 'error', message: data.error})
            } else {
                setSessionId(data.sessionId)
                return data.clientSecret
            }
        })
    }, [checkoutProps, form, urlCreateCheckoutSession]);
    const onComplete = useCallback(() => {
        post({
            url: `${urlCreateCheckoutStatus}?session_id=${sessionId}`,
            method: 'GET',
            form
        }).then(({data}) => {
            form.setState({...form.state, userInfo: data.userInfo})
            if (onCheckout)
                onCheckout(data)
        });
    }, [sessionId, form, onCheckout, urlCreateCheckoutStatus])
    return <EmbeddedCheckoutProvider
        stripe={stripe}
        options={{onComplete, fetchClientSecret}}
        {...props}>
        {children ? children : <EmbeddedCheckout/>}
    </EmbeddedCheckoutProvider>
};