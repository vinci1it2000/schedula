import {Steps as BaseSteps, Flex, Button, theme} from 'antd';
import {useState, useContext} from 'react';
import {useLocaleStore} from "../../models/locale";
import get from 'lodash/get';

const Steps = (
    {
        children,
        render,
        items,
        controls = true,
        data2verify,
        doneButton,
        ...props
    }
) => {
    const {formContext: {FormContext}} = render
    const {form: {state: {errorSchema}}} = useContext(FormContext)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Tour')
    const {token} = theme.useToken();
    const [current, setCurrent] = useState(0);
    const onChange = (value) => {
        setCurrent(value);
    };
    const _items = items.map((item, index) => (
        {key: index, ...item, ...(index === current ? {status: 'process'} : {})}
    ))
    const contentStyle = {
        color: token.colorTextTertiary,
        backgroundColor: token.colorFillAlter,
        borderRadius: token.borderRadiusLG,
        border: `1px dashed ${token.colorBorder}`,
        overflowY: 'hidden',
        flexGrow: 1,
        padding: 16
    };
    let kw = {}, hasErrors;
    if (data2verify) {
        hasErrors = (data2verify[current] || []).some(k => !!get(errorSchema, k, false))
        kw.status = hasErrors ? 'error' : 'progress'
    }
    let _controls
    if (controls) {
        let nextBtn, isLastStep = current === _items.length - 1
        if (isLastStep && doneButton) {
            nextBtn = doneButton
        } else {
            nextBtn =
                <Button
                    type="primary"
                    disabled={isLastStep || hasErrors}
                    onClick={() => {
                        setCurrent(current + 1);
                    }}>
                    {locale.Next}
                </Button>
        }
        _controls = <Flex gap="middle" justify={'space-around'}>
            <Button disabled={!(current > 0)} onClick={() => {
                setCurrent(current - 1);
            }}>
                {locale.Previous}
            </Button>
            {nextBtn}
        </Flex>
    }
    return <Flex gap="large" vertical style={{
        height: "100%",
        overflowY: "hidden"
    }}>
        <BaseSteps
            current={current}
            onChange={onChange}
            items={_items}
            {...kw}
            {...props}
        />
        <div style={contentStyle}>{children[current]}</div>
        {_controls}
    </Flex>
};
export default Steps;