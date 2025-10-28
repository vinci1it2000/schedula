import React from 'react'
import ReactDOM from 'react-dom'
import lodash from 'lodash'
import * as plasmicLoaderReact from '@plasmicapp/loader-react'
import renderForm, {
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains,
    createLayoutElement
} from './core'
import './main.css'

window.lodash = lodash
window.React = React
window.ReactDOM = ReactDOM
window.plasmicLoaderReact = plasmicLoaderReact
window.schedula = {
    renderForm,
    createLayoutElement,
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains
}


