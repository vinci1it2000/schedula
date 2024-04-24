import {loadStripe} from "@stripe/stripe-js";
import React, {useState, useEffect} from "react";
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
    const [clientSecret, setClientSecret] = useState('');
    const [sessionId, setSessionId] = useState('');
    const {form, stripeKey} = render.formContext
    const {stripe} = form.state
    const initCheckout = () => post({
        url: urlCreateCheckoutSession,
        data: checkoutProps,
        form
    }).then(({data}) => {
        if (data.error) {
            form.props.notify({type: 'error', message: data.error})
        } else {
            setClientSecret(data.clientSecret)
            setSessionId(data.sessionId)
        }
    });
    useEffect(() => {
        if (stripe) {
            initCheckout()
        } else {
            loadStripe(stripeKey).then(stripe => {
                form.setState({...form.state, stripe}, () => {
                    initCheckout()
                })
            });
        }
    }, [checkoutProps]);
    const onComplete = () => {
        post({
            url: `${urlCreateCheckoutStatus}?session_id=${sessionId}`,
            method: 'GET',
            form
        }).then(({data}) => {
            form.setState({...form.state, userInfo: data.userInfo})
            if (onCheckout)
                onCheckout(data)
        });
    }
    return <div className={'stripe-checkout'}
                style={{height: '100%', overflowY: 'auto'}}>
        {sessionId ? (<EmbeddedCheckoutProvider
            stripe={stripe}
            options={{onComplete, clientSecret}}
            {...props}>
            <EmbeddedCheckout/>
        </EmbeddedCheckoutProvider>) : <div>Loading...</div>}
    </div>
};