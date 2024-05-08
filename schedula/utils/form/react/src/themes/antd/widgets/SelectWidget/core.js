import Select from 'antd/lib/select';
import {
    ariaDescribedByIds,
    enumOptionsIndexForValue,
    enumOptionsValueForIndex
} from '@rjsf/utils';
import isString from 'lodash/isString';
import './SelectWidget.css'

const SELECT_STYLE = {
    width: '100%',
};

/** The `SelectWidget` is a widget for rendering dropdowns.
 *  It is typically used with string properties constrained with enum options.
 *
 * @param props - The `WidgetProps` for this component
 */
export default function SelectWidget(
    {
        autofocus,
        disabled,
        formContext = {},
        id,
        multiple,
        onBlur,
        onChange,
        onFocus,
        options,
        placeholder,
        readonly,
        value,
    }) {
    const {readonlyAsDisabled = true} = formContext;

    let {
        enumOptions,
        enumDisabled,
        emptyValue,
        overwriteEnumOptions,
        ...props
    } = options;
    if (overwriteEnumOptions)
        enumOptions = overwriteEnumOptions.map((option) => {
            if (typeof option === 'string')
                return {value: option, label: option}
            return option
        })

    const handleChange = (nextValue) => onChange(enumOptionsValueForIndex(nextValue, enumOptions, emptyValue));

    const handleBlur = () => onBlur(id, enumOptionsValueForIndex(value, enumOptions, emptyValue));

    const handleFocus = () => onFocus(id, enumOptionsValueForIndex(value, enumOptions, emptyValue));

    const filterOption = (input, option) => {
        if (option && isString(option.children)) {
            return option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0;
        }
        return false;
    };

    const getPopupContainer = (node) => node.parentNode;

    const selectedIndexes = enumOptionsIndexForValue(value, enumOptions, multiple);

    // Antd's typescript definitions do not contain the following props that are actually necessary and, if provided,
    // they are used, so hacking them in via by spreading `extraProps` on the component to avoid typescript errors
    const extraProps = {
        ...props,
        name: id
    };
    return <Select
        autoFocus={autofocus}
        disabled={disabled || (readonlyAsDisabled && readonly)}
        getPopupContainer={getPopupContainer}
        id={id}
        showSearch
        mode={typeof multiple !== 'undefined' ? 'multiple' : undefined}
        onBlur={!readonly ? handleBlur : undefined}
        onChange={!readonly ? handleChange : undefined}
        onFocus={!readonly ? handleFocus : undefined}
        placeholder={placeholder}
        style={SELECT_STYLE}
        value={selectedIndexes}
        filterOption={filterOption}
        aria-describedby={ariaDescribedByIds(id)}
        {...extraProps}>
        {Array.isArray(enumOptions) &&
            enumOptions.map(({
                                 value: optionValue,
                                 label: optionLabel
                             }, index) => (
                <Select.Option
                    disabled={Array.isArray(enumDisabled) && enumDisabled.indexOf(optionValue) !== -1}
                    key={String(index)}
                    value={String(index)}>
                    {optionLabel}
                </Select.Option>
            ))}
    </Select>
}