import React from 'react'
import ReactDOM from 'react-dom'
import lodash from 'lodash'
import renderForm, {
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains
} from './core'
import './main.css'

window.lodash = lodash
window.React = React
window.ReactDOM = ReactDOM
window.schedula = {
    renderForm,
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains
}


