import React from "react";
import {domainDomain} from './Domain'

const Description = React.lazy(() => import('./Description'));
const DiffViewer = React.lazy(() => import('./DiffViewer'));
const Domain = React.lazy(() => import('./Domain'));
const Element = React.lazy(() => import('./Element'));
const FlexLayout = React.lazy(() => import('./FlexLayout'));
const GridLayout = React.lazy(() => import('./GridLayout'));
const Static = React.lazy(() => import('./Static'));
const Stripe = React.lazy(() => import('./Stripe'));
const Title = React.lazy(() => import('./Title'));
const Form = React.lazy(() => import('../form'));

export function generateComponents() {
    return {
        Form,
        Description,
        DiffViewer,
        Domain,
        Element,
        FlexLayout,
        GridLayout,
        Static,
        Stripe,
        Title
    }
}

export function generateComponentsDomains() {
    return {
        Domain: domainDomain
    }
}

export default generateComponents();