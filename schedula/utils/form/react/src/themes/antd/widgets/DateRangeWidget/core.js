import React from "react";
import dayjs from "dayjs";
import {ariaDescribedByIds} from "@rjsf/utils";
import {DatePicker} from "antd";
import utc from 'dayjs/plugin/utc';
import {useLocaleStore} from '../../models/locale'

dayjs.extend(utc)
const DATE_PICKER_STYLE = {
    width: "100%"
};


export default function RangeDateWidget(props) {
    const {
        disabled,
        formContext,
        id,
        onBlur,
        onChange,
        onFocus,
        placeholder,
        readonly,
        options = {},
        schema,
        value,
    } = props;
    const {format = 'date'} = schema.items || {}
    const {readonlyAsDisabled = true} = formContext;
    const {picker, ...extraProps} = options
    let formatValue;
    if (format === 'date-time') {
        formatValue = (v) => v.toISOString()
    } else if (format === 'date' && picker) {
        formatValue = (v, index) => (index ? v.endOf(picker) : v.startOf(picker)).format("YYYY-MM-DD")
    } else {
        formatValue = (v) => v.format("YYYY-MM-DD")
    }
    const {getLocale} = useLocaleStore()
    const locale = getLocale('DatePicker')

    const handleChange = (nextValue) =>
        onChange((nextValue || []).map((v, index) => (formatValue(v, index))));

    const handleBlur = () => onBlur(id, value);

    const handleFocus = () => onFocus(id, value);

    const getPopupContainer = (node) => node.parentNode;

    return <DatePicker.RangePicker
        locale={locale}
        disabled={disabled || (readonlyAsDisabled && readonly)}
        getPopupContainer={getPopupContainer}
        id={id}
        picker={format === 'date' ? picker : undefined}
        name={id}
        onBlur={!readonly ? handleBlur : undefined}
        onChange={!readonly ? handleChange : undefined}
        onFocus={!readonly ? handleFocus : undefined}
        placeholder={placeholder}
        showTime={format === 'date-time'}
        style={DATE_PICKER_STYLE}
        value={(value || []).map(dayjs)}
        aria-describedby={ariaDescribedByIds(id)}
        {...extraProps}
    />
}