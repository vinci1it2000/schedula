import React from "react";
import {domainDomain} from './Domain'

const Description = React.lazy(() => import('./Description'));
const DiffViewer = React.lazy(() => import('./DiffViewer'));
const Domain = React.lazy(() => import('./Domain'));
const Element = React.lazy(() => import('./Element'));
const FlexLayout = React.lazy(() => import('./FlexLayout'));
const GridLayout = React.lazy(() => import('./GridLayout'));
const Plasmic_Component = React.lazy(() => import('./Plasmic/component'));
const Plasmic_Page = React.lazy(() => import('./Plasmic/page'));
const Router_Link = React.lazy(() => import('./Router/link'));
const Router_Route = React.lazy(() => import('./Router/route'));
const Router_Routes = React.lazy(() => import('./Router/routes'));
const Static = React.lazy(() => import('./Static'));
const Stripe = React.lazy(() => import('./Stripe'));
const Stripe_Portal = React.lazy(() => import('./Stripe/portal'));
const Stripe_Table = React.lazy(() => import('./Stripe/table'));
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
        "Plasmic.Component": Plasmic_Component,
        "Plasmic.Page": Plasmic_Page,
        "Router.Link": Router_Link,
        "Router.Route": Router_Route,
        "Router.Routes": Router_Routes,
        Static,
        Stripe,
        "Stripe.Portal": Stripe_Portal,
        "Stripe.Table": Stripe_Table,
        Title
    }
}

export function generateComponentsDomains() {
    return {
        Domain: domainDomain
    }
}

export default generateComponents();