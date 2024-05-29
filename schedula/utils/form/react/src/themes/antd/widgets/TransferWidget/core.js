import {Transfer} from "antd";
import {
    ariaDescribedByIds,
    enumOptionsIndexForValue,
    enumOptionsValueForIndex
} from "@rjsf/utils";
import {useLocaleStore} from "../../models/locale";

export default function TransferWidget(
    {
        disabled,
        formContext,
        id,
        onChange,
        options,
        readonly,
        value,
    }) {
    const {readonlyAsDisabled = true} = formContext;

    const {enumOptions, emptyValue} = options;

    const handleChange = (nextValue) =>
        onChange(enumOptionsValueForIndex(nextValue, enumOptions, emptyValue));

    const extraProps = {id, ...options};
    const selectedIndexes = enumOptionsIndexForValue(value, enumOptions, true);
    const mockData = enumOptions.map(({label}, i) => ({
        key: String(i), title: label
    }))
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Transfer')
    return Array.isArray(enumOptions) && enumOptions.length > 0 ? (
        <Transfer
            locale={locale}
            showSearch
            disabled={disabled || (readonlyAsDisabled && readonly)}
            dataSource={mockData}
            targetKeys={selectedIndexes}
            onChange={!readonly ? handleChange : undefined}
            render={(item) => item.title}
            aria-describedby={ariaDescribedByIds(id)}
            {...extraProps}/>
    ) : null;
}