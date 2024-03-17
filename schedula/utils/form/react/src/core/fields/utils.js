import React, {Suspense} from "react";
import {
    ADDITIONAL_PROPERTY_FLAG,
    PROPERTIES_KEY
} from "@rjsf/utils";
import get from "lodash/get";
import has from "lodash/has";
import isObject from "lodash/isObject";
import cloneDeep from "lodash/cloneDeep";
import set from "lodash/set";
import assign from "lodash/assign";


export function getComponents() {
    return components
}

export function getComponentDomains() {
    return domains
}

export function createLayoutElement({key, layout, render, isArray}) {
    const {
        path,
        component,
        props: props_ = {},
        eprops = {},
        fprops = {},
        vprops = {},
        eothers = {},
        fothers = {},
        vothers = {},
        children,
        force_render,
        ...others_
    } = layout;
    let props, others;
    const {formContext: {form}} = render
    if (Object.keys(eothers).length) {
        others = cloneDeep(others_)
        Object.entries(eothers).forEach(([path, layout], index) => {
            set(others, path, createLayoutElement({
                key: `${key}-ele-${index}`,
                layout,
                render
            }))
        });
    } else {
        others = others_
    }
    if (Object.keys(fothers).length) {
        others = cloneDeep(others)
        Object.entries(fothers).forEach(([path, func]) => {
            set(others, path, form.compileFunc(func).bind(null, render, layout))
        });
    }
    if (Object.keys(vothers).length) {
        others = cloneDeep(others)
        Object.entries(vothers).forEach(([path, func]) => {
            set(others, path, form.compileFunc(func)(render, layout))
        });
    }
    if (Object.keys(eprops).length) {
        props = cloneDeep(props_)
        Object.entries(eprops).forEach(([path, layout], index) => {
            set(props, path, createLayoutElement({
                key: `${key}-ele-${index}`,
                layout,
                render
            }))
        });
    } else {
        props = props_
    }
    if (Object.keys(fprops).length) {
        props = cloneDeep(props)
        Object.entries(fprops).forEach(([path, func]) => {
            set(props, path, form.compileFunc(func).bind(null, render, layout))
        });
    }
    if (Object.keys(vprops).length) {
        props = cloneDeep(props)
        Object.entries(vprops).forEach(([path, func]) => {
            set(props, path, form.compileFunc(func)(render, layout))
        });
    }

    if (path) {
        let fieldPath = path.split('/'), name = fieldPath[0];
        fieldPath = fieldPath.slice(1).join('/')
        let contentProps
        const {SchemaField} = render
        if (name === '..') {
            const {
                schema,
                uiSchema = {},
                formData,
                errorSchema,
                idSchema,
                name,
                disabled = false,
                readonly = false,
                hideError,
                idPrefix,
                idSeparator,
                formContext,
                registry,
            } = render.parent.props;
            const {parent} = formContext

            contentProps = {
                key: `${key}-${name}`,
                idPrefix,
                idSeparator,
                formContext,
                schema,
                uiSchema,
                errorSchema,
                idSchema,
                formData,
                registry,
                disabled,
                readonly,
                onChange: parent.props.onChange,
                onBlur: parent.props.onBlur,
                onFocus: parent.props.onFocus,
                hideError,
            }
        } else if (name === '.') {
            const {
                readonly,
                disabled,
                idSchema,
                uiSchema,
                schema,
                formData,
                formContext,
                registry,
                errorSchema,
                idPrefix,
                idSeparator,
                hideError,
                parent
            } = render

            contentProps = {
                key: `${key}-${name}`,
                idPrefix,
                idSeparator,
                formContext,
                schema,
                uiSchema,
                errorSchema,
                idSchema,
                formData,
                registry,
                disabled,
                readonly,
                onChange: parent.props.onChange,
                onBlur: parent.props.onBlur,
                onFocus: parent.props.onFocus,
                hideError,
            }
        } else if (name === '#') {
            const {
                readonly,
                disabled,
                idPrefix,
                idSeparator,
                formContext
            } = form.props
            const {
                schema,
                uiSchema,
                formData,
                errorSchema,
                idSchema
            } = form.state;
            const registry = form.getRegistry();
            contentProps = {
                key: `${key}-${name}`,
                idPrefix,
                idSeparator,
                formContext,
                schema,
                uiSchema,
                errorSchema,
                idSchema,
                formData,
                registry,
                disabled,
                readonly,
                onChange: form.onChange,
                onBlur: form.onBlur,
                onFocus: form.onFocus,
            }
        } else if (isArray) {
            const {
                readonly,
                disabled,
                idSchema,
                uiSchema,
                schema,
                name: arrayName,
                formContext,
                registry,
                errorSchema,
                idPrefix,
                idSeparator,
                hideError,
                parent,
                onBlur,
                onFocus,
                autofocus,
                rawErrors
            } = render
            const index = Number(name)
            const {keyedFormData} = parent.state
            if (keyedFormData[index] === undefined)
                return null
            const {schemaUtils} = registry
            const {key, item} = keyedFormData[index];
            const itemCast = item;
            const itemSchema = schemaUtils.retrieveSchema(schema.items, itemCast);
            const itemErrorSchema = errorSchema ? (errorSchema[index]) : undefined;
            const itemIdPrefix = idSchema.$id + idSeparator + index;
            const itemIdSchema = schemaUtils.toIdSchema(
                itemSchema,
                itemIdPrefix,
                itemCast,
                `${index}-${idPrefix}`,
                idSeparator
            );
            const itemFormContext = {...formContext, arrayItemIndex: index}
            const itemRegistry = {...registry, formContext: itemFormContext}

            contentProps = {
                key: `${key}-${index}`,
                name: name && `${arrayName}-${index}`,
                index,
                required: parent.isItemRequired(itemSchema),
                schema: itemSchema,
                uiSchema: uiSchema.items || {},
                errorSchema: itemErrorSchema,
                idSchema: itemIdSchema,
                idPrefix,
                idSeparator,
                formData: itemCast,
                formContext: itemFormContext,
                onChange: parent.onChangeForIndex(index),
                onBlur,
                onFocus,
                registry: itemRegistry,
                disabled,
                readonly,
                hideError,
                rawErrors,
                autofocus: autofocus && index === 0
            }
        } else {
            const {
                readonly,
                disabled,
                idSchema,
                uiSchema,
                schema,
                formData,
                formContext,
                registry,
                errorSchema,
                idPrefix,
                idSeparator,
                onBlur,
                onFocus,
                hideError,
                parent
            } = render
            const addedByAdditionalProperties = has(schema, [
                PROPERTIES_KEY,
                name,
                ADDITIONAL_PROPERTY_FLAG,
            ]);
            let fieldUiSchema = fixLayoutOption(addedByAdditionalProperties
                ? uiSchema.additionalProperties
                : uiSchema[name]);

            const fieldIdSchema = get(idSchema, [name], {});
            contentProps = {
                key: `${key}-${name}`,
                name,
                required: parent.isRequired(name),
                schema: get(schema, [PROPERTIES_KEY, name], {}),
                uiSchema: fieldUiSchema || {},
                errorSchema: get(errorSchema, name),
                idSchema: fieldIdSchema,
                idPrefix,
                idSeparator,
                formData: get(formData, name),
                formContext,
                wasPropertyKeyModified: parent.state.wasPropertyKeyModified,
                onKeyChange: parent.onKeyChange(name),
                onChange: parent.onPropertyChange(name, addedByAdditionalProperties),
                onBlur,
                onFocus,
                registry,
                disabled,
                readonly,
                hideError,
                onDropPropertyClick: parent.onDropPropertyClick,
            }
        }

        if (others.uiSchema) {
            others.uiSchema = fixLayoutOption(others.uiSchema)
        }
        if (fieldPath || component || children) {
            contentProps.uiSchema["ui:layout"] = {
                ...layout,
                "path": fieldPath
            }
            contentProps.uiSchema["ui:onlyChildren"] = (!!fieldPath || name === '.' || (children ||[]).length)
        } else {
            contentProps = assign(contentProps, others)
        }
        let element = React.createElement(SchemaField, contentProps)
        return Object.keys(element.props.schema).length ? element : null
    } else {
        let elements = (children || []).map((element, index) => {
                if (isObject(element)) {
                    return createLayoutElement({
                        key: `${key}-${index}`, render, layout: element
                    })
                }
                return element
            }),
            type = getComponents()[component],
            domain = getComponentDomains()[component];

        props.key = key
        if (type) {
            props.render = render
        } else {
            type = "div"
        }
        if (domain && !domain({...props, children: elements})) {
            return null
        }
        if (elements.filter(v => v !== null).length) {
            return <Suspense key={key}>
                {React.createElement(type, props, elements)}
            </Suspense>
        } else if (force_render) {
            return <Suspense key={key}>
                {React.createElement(type, props)}
            </Suspense>
        } else {
            return null
        }
    }

}


var components = {};


export function registerComponent(name, component) {
    components[name] = component
}

var domains = {};


export function registerComponentDomain(name, domain) {
    domains[name] = domain
}

function fixLayoutOption(obj) {
    if (obj && (obj["ui:option"] || {}).layout) {
        if (!obj.hasOwnProperty("ui:layout"))
            obj["ui:layout"] = obj["ui:option"].layout
        delete obj["ui:option"]["layout"]
    }
    return obj
}

