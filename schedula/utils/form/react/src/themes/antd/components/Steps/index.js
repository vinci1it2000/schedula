import {Steps as BaseSteps, Flex, Button, theme} from 'antd';
import {
    useState,
    useContext,
    useEffect,
    isValidElement,
    useCallback,
    useMemo
} from 'react';
import {useLocaleStore} from "../../models/locale";
import get from 'lodash/get';


const Steps = (
    {
        children,
        render,
        items,
        controls = true,
        data2verify,
        finishButton = false,
        previousButton = {},
        nextButton = {},
        setCurrentStep = null,
        ...props
    }
) => {
    const {formContext: {FormContext}, idSchema: {$id}, idPrefix} = render
    const {form: {state: {errorSchema}}} = useContext(FormContext)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Tour')
    const {token} = theme.useToken();
    const [current, setCurrent] = useState(0);
    useEffect(() => {
        if (setCurrentStep)
            setCurrentStep(current)
    }, [current, setCurrentStep])
    const onChange = useCallback((value) => {
        setCurrent(value);
    }, [setCurrent]);
    const _items = useMemo(() => items.map(
        (item, index) => ({
            key: index, ...item, ...(index === current ? {status: 'process'} : {})
        })
    ), [items, current])
    const contentStyle = useMemo(() => ({
        color: token.colorTextTertiary,
        backgroundColor: token.colorFillAlter,
        borderRadius: token.borderRadiusLG,
        border: `1px dashed ${token.colorBorder}`,
        overflowY: 'hidden',
        flexGrow: 1,
        padding: 16
    }), [token]);

    const {status, hasErrors} = useMemo(() => {
        let status, hasErrors;
        if (data2verify) {
            const regexPattern = new RegExp(`^${idPrefix}\\.?`);
            hasErrors = (data2verify[current] || []).some(k => {
                let path = (k.startsWith(idPrefix) ? k : $id + '.' + k).replace(regexPattern, '')
                return !!get(errorSchema, path, false)
            })
            status = hasErrors ? 'error' : 'progress'
        }
        return {status, hasErrors}
    }, [data2verify, current, idPrefix, $id, errorSchema])

    const _controls = useMemo(() => {
        if (controls) {
            let isLastStep = current === _items.length - 1,
                previousBtn = previousButton,
                nextBtn = isLastStep ? (finishButton === false ? {style: {display: "none"}} : finishButton) : nextButton;
            if (!isValidElement(previousBtn)) {
                previousBtn = <Button
                    key={'previous'}
                    disabled={current <= 0}
                    onClick={() => {
                        setCurrent(current - 1)
                    }}
                    children={locale.Previous}
                    {...previousBtn}/>

            }
            if (!isValidElement(nextBtn)) {
                nextBtn = <Button
                    key={isLastStep ? 'finish' : 'next'}
                    disabled={hasErrors}
                    type={"primary"}
                    onClick={isLastStep ? null : () => {
                        setCurrent(current + 1)
                    }}
                    children={isLastStep ? locale.Finish : locale.Next}
                    {...nextBtn}/>
            }
            return <Flex key={'controls'} gap="middle" justify={'space-around'}>
                <div key={'left'} style={{
                    width: '50%',
                    textAlign: 'center'
                }}>{previousBtn}</div>
                <div key={'right'} style={{
                    width: '50%',
                    textAlign: 'center'
                }}>{nextBtn}</div>
            </Flex>
        }
    }, [current, _items, controls, previousButton, finishButton, nextButton, setCurrent, locale, hasErrors]);
    return <Flex gap="large" vertical style={{
        height: "100%", overflowY: "hidden"
    }}>
        <BaseSteps
            key={'step'}
            current={current}
            onChange={onChange}
            items={_items}
            state={status}
            {...props}
        />
        <div key={'content'} style={contentStyle}>{children[current]}</div>
        {_controls}
        <div key={'placeholder'}></div>
    </Flex>
};
export default Steps;