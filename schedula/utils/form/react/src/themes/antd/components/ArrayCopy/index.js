import {useState} from "react";
import {Modal, Checkbox, Select, Col, Row, Tooltip} from 'antd';
import {CopyOutlined, ExclamationCircleFilled} from '@ant-design/icons';
import get from "lodash/get";
import has from "lodash/has";
import set from "lodash/set";
import cloneDeep from "lodash/cloneDeep";
import {nanoid} from "nanoid";
import {getUiOptions} from "@rjsf/utils";
import {useLocaleStore} from "../../models/locale";
import isArray from "lodash/isArray";

const getArray = (parent) => {
    if (get(parent, 'props.schema.type') === 'array') {
        return parent
    } else if (has(parent, 'props.formContext.parent')) {
        return getArray(get(parent, 'props.formContext.parent'))
    } else {
        return null
    }
}
const ArrayCopy = ({children, render, copyItems = {}, ...props}) => {
    const {getLocale} = useLocaleStore()
    const locale = getLocale('ArrayCopy')
    const parentArray = getArray(get(render, 'formContext.parent', {}));
    const [checkedValues, setCheckedValues] = useState([])
    if (isArray(copyItems))
        copyItems = copyItems.reduce((r, k) => {
            r[k] = k;
            return r
        }, {})
    if (Object.keys(copyItems).length && parentArray !== null) {
        let checked = checkedValues;
        const {keyedFormData} = parentArray.state;
        const {name = 'item', uiSchema = {}} = parentArray.props;
        const {arrayItemIndex} = render.formContext
        const {itemLabel} = getUiOptions(uiSchema);
        const options = keyedFormData.map(
            ({item}, index) => {
                let label = (itemLabel && item[itemLabel] ? `${index}. ${item[itemLabel]}` : null) || `${name}-${index + 1}`
                return {label, value: index}
            }
        ).filter(({value}) => (value !== arrayItemIndex));
        if (options.length >= 1) {
            let element;
            if (options.length <= 5) {
                element = <Checkbox.Group
                    options={options}
                    defaultValue={checkedValues}
                    onChange={(values) => {
                        setCheckedValues(values)
                        checked = values
                    }}>
                    <Row>{options.map(({value, label}, index) => (
                        <Col key={index} span={24}>
                            <Checkbox key={index}
                                      value={value}>{label}</Checkbox>
                        </Col>
                    ))}</Row>
                </Checkbox.Group>
            } else {
                element = <Select
                    mode="multiple"
                    allowClear
                    style={{width: '100%'}}
                    placeholder={locale.placeholder}
                    defaultValue={checkedValues}
                    onChange={(values) => {
                        setCheckedValues(values)
                        checked = values
                    }}
                    options={options}
                />
            }
            return <Tooltip key={'copy'} title={locale.tooltip}>
                <CopyOutlined
                    key={'copy'}
                    onClick={(event) => {
                        event.stopPropagation();
                        Modal.confirm({
                            centered: true,
                            title: locale.titleCopyButton,
                            icon: <ExclamationCircleFilled/>,
                            content: element,
                            onOk() {
                                if (checked.length) {
                                    const {onChange} = parentArray.props;
                                    const data = Object.entries(copyItems).map(([pathFrom, pathTo]) => ([pathTo, get(render.formData, pathFrom)]))
                                    const newKeyedFormData = keyedFormData.map(
                                        ({key, item}, index) => {
                                            if (arrayItemIndex !== index && checked.includes(index)) {
                                                item = cloneDeep(item)
                                                key = nanoid()
                                                data.forEach(([path, value]) => {
                                                    set(item, path, value)
                                                })
                                            }
                                            return {key, item}
                                        }
                                    )
                                    parentArray.setState({
                                        ...parentArray.state,
                                        keyedFormData: newKeyedFormData,
                                        updatedKeyedFormData: true,
                                    }, () => {
                                        onChange((newKeyedFormData.map((keyedItem) => keyedItem.item)))
                                    })
                                }
                            }
                        })
                    }}
                    {...props}
                />
            </Tooltip>
        }
    }
    return null
};
export default ArrayCopy;