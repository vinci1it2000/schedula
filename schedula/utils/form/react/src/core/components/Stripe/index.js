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
        type,
        urlCreateCheckoutSession = "/stripe/create-checkout-session",
        urlCreateCheckoutStatus = "/stripe/session-status",
        items,
        options,
        ...props
    }) {
    const [status, setStatus] = useState(null);
    const [clientSecret, setClientSecret] = useState('');
    const [sessionId, setSessionId] = useState('');
    const {form, stripeKey} = render.formContext
    const {stripe} = form.state
    const setItems = () => post({
        url: urlCreateCheckoutSession,
        data: items,
        form
    }).then(({data}) => {
        setClientSecret(data.clientSecret)
        setSessionId(data.sessionId)
    });
    useEffect(() => {
        if (stripe) {
            setItems()
        } else {
            loadStripe(stripeKey).then(stripe => {
                form.setState({...form.state, stripe}, () => {
                    setItems()
                })
            });
        }
    }, [items]);
    const onComplete = () => {
        post({
            url: `${urlCreateCheckoutStatus}?session_id=${sessionId}`,
            method: 'GET',
            form
        }).then(({data}) => {
            setStatus(data.status);
            form.setState({...form.state, userInfo: data.userInfo})
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