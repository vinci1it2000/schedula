import React from "react";
import {domainDomain} from './Domain'

const Description = React.lazy(() => import('./Description'));
const DiffViewer = React.lazy(() => import('./DiffViewer'));
const Domain = React.lazy(() => import('./Domain'));
const Element = React.lazy(() => import('./Element'));
const FlexLayout = React.lazy(() => import('./FlexLayout'));
const Title = React.lazy(() => import('./Title'));


export function generateComponents() {
    return {
        Description,
        DiffViewer,
        Domain,
        Element,
        FlexLayout,
        Title
    }
}

export function generateComponentsDomains() {
    return {
        Domain: domainDomain
    }
}

export default generateComponents();