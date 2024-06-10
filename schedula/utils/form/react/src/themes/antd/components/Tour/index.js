import {useState} from 'react'
import {Tour as BaseTour, Button} from 'antd';

const Tour = ({children, render, steps, buttonProps, ...props}) => {
    const [open, setOpen] = useState(false);
    return <>
        <Button type="primary" onClick={() => setOpen(true)} {...buttonProps}>
            Tour
        </Button>
        <BaseTour
            open={open}
            onClose={() => setOpen(false)}
            steps={steps.map(({target, ...step}) => {
                if (typeof target === 'string') {
                    target = document.querySelector(target);
                } else if (typeof target === 'function') {
                    target = target();
                }
                return {...step, target};
            })}
            indicatorsRender={(current, total) => (
                <span>{current + 1} / {total}</span>
            )}
            {...props}
        />
    </>
};
export default Tour;