import {Collapse} from 'antd';

const Accordion = ({children, render, items = {}, ...props}) => (
    <Collapse size="small" accordion {...props} >
        {children.map((element, index) => (
            element ? <Collapse.Panel key={index} {...items[index]}>
                {element}
            </Collapse.Panel> : null
        ))}
    </Collapse>
);
export default Accordion;