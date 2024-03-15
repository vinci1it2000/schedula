import {useMemo, useState} from "react";
import {Layout, Model} from "flexlayout-react";
import 'flexlayout-react/style/light.css'
import './FlexLayout.css'
import isEqualWith from 'lodash/isEqualWith'
import get from 'lodash/get'
import omit from 'lodash/omit'


const parseModel = (render, items, element, key = '0') => {
    let {children = null, component = null, domain = null} = element;
    const {formContext: {form}} = render
    if (!(!domain || form.compileFunc(domain)(render))) {
        return null
    }
    if (children) {
        children = children.map((ele, index) => parseModel(render, items, ele, `${key}-${index}`)).filter(ele => ele !== null)
    }
    if (component !== null) {
        return items[component] ? {id: key, ...element} : null
    }
    return children.length ? {id: key, ...element, children} : null
}
const removeSkipEqual = (element) => {
    let {children = null, skipEqual = false} = element;

    if (children) {
        children = children.map(removeSkipEqual).filter(ele => ele !== null)
    }
    if (!skipEqual) {
        return {...element}
    }
    return children.length ? {...element, children} : null
}
const customizer = (objValue, othValue, key, object, other, stack) => {
    if (get(objValue, 'skipEqual', false) || get(othValue, 'skipEqual', false))
        return true
}

const FlexLayout = ({children, render, model: rawJSONModel, ...props}) => {
    const newJSONModel = {
        ...rawJSONModel,
        global: {
            tabEnableRename: false,
            tabSetHeaderHeight: 33,
            tabSetTabStripHeight: 33,
            borderBarSize: 33,
            ...(rawJSONModel.global || {})
        },
        layout: parseModel(render, children, rawJSONModel.layout || {}, 'layout'),
        borders: (rawJSONModel.borders || []).map((ele, index) => parseModel(render, children, ele, `borders-${index}`)).filter(ele => ele !== null)
    }

    const [JSONModel, setJSONModel] = useState(newJSONModel)

    if (!(isEqualWith({
        layout: removeSkipEqual(JSONModel.layout),
        borders: JSONModel.borders.map(removeSkipEqual).filter(ele => ele !== null),
        ...omit(JSONModel, ['layout', 'borders'])
    }, {
        layout: removeSkipEqual(newJSONModel.layout),
        borders: newJSONModel.borders.map(removeSkipEqual).filter(ele => ele !== null),
        ...omit(newJSONModel, ['layout', 'borders'])
    }, customizer))) {
        setJSONModel(newJSONModel)
    }
    const model = useMemo(() => {
        return Model.fromJson(JSONModel)
    }, [JSONModel])
    const factory = (node) => (children[node.getComponent()]);
    return <Layout model={model} factory={factory} {...props}/>
};
export default FlexLayout;