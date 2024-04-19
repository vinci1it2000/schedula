import React from 'react'
import ReactDOM from 'react-dom'
import renderForm, {registerComponent, registerComponentDomain} from './core'
import './main.css'

window.React = React
window.ReactDOM = ReactDOM
window.schedula = {
    renderForm, registerComponent, registerComponentDomain
}


