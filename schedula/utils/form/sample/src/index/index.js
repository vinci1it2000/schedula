import editOnChange from './editOnChange'
import preSubmit from './preSubmit'
import postSubmit from './postSubmit'
import fields from './fields'
import widgets from './widgets'
import formContext from './formContext'
import customValidate from './customValidate'
import transformErrors from './transformErrors'
import * as uiFunctions from './uiFunctions'
import './index.css'

window.schedulaProps = {
    editOnChange,
    preSubmit,
    postSubmit,
    widgets,
    fields,
    formContext,
    uiFunctions,
    customValidate,
    transformErrors
}