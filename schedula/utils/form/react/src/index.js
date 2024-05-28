import React from 'react'
import ReactDOM from 'react-dom'
import lodash from 'lodash'
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
window.schedula = {
    renderForm,
    createLayoutElement,
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains
}


