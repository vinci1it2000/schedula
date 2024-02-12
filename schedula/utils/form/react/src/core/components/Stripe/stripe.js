import {createGlobalStore} from "hox";
import {useState} from "react";
import {loadStripe} from "@stripe/stripe-js";

function useStripe() {
    const [stripe, setStripe] = useState(null);
    function  getStripe(stripeKey){
        if (stripe){
            return stripe
        } else{
            setStripe(loadStripe)
        }
    }
    return {stripe, setStripe};
}

export const [useStripeStore] = createGlobalStore(useStripe);