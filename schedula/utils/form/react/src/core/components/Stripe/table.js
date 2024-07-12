import React, {useEffect, useState} from "react";
import './table.css'


function loadScript(src) {
    return new Promise((resolve, reject) => {
        // Check if the script is already present
        if (document.querySelector(`script[src="${src}"]`)) {
            resolve();
            return;
        }

        // Create a new script element
        const script = document.createElement('script');
        script.src = src;
        script.type = 'text/javascript';
        script.async = true;

        // Handle the script load event
        script.onload = () => {
            resolve();
        };

        // Handle the script error event
        script.onerror = (err) => {
            console.error(`Failed to load script ${src}.`);
            reject(err);
        };

        // Append the script to the head or body
        document.head.appendChild(script);
    });
}


export default function StripeTable(
    {
        children,
        render: {
            formContext: {stripeKey, form}
        },
        urlPriceTableSession = "/stripe/create-customer-pricing-table-session",
        tableId,
        ...props
    }) {
    const {state: {userInfo: {id: user_id = null}}} = form
    const [clientSecret, setClientSecret] = useState(null);

    useEffect(() => {
        loadScript("https://js.stripe.com/v3/pricing-table.js").then(() => {
            if (user_id && urlPriceTableSession) {
                form.postData({
                    url: urlPriceTableSession,
                    data: {},
                }).then(({data: {error, clientSecret}}) => {
                    if (error) {
                        form.props.notify({
                            description: error,
                        })
                    } else if (clientSecret) {
                        setClientSecret(clientSecret)
                    }
                }).catch(({message}) => {
                    form.props.notify({
                        description: message,
                    })
                })
            }
        })
    }, [user_id, urlPriceTableSession, form])
    return <stripe-pricing-table
        pricing-table-id={tableId}
        publishable-key={stripeKey}
        customer-session-client-secret={clientSecret}
        client-reference-id={user_id}
        {...props}
    />
};