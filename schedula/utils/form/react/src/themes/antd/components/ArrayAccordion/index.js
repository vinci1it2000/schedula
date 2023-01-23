import {Collapse, Space} from 'antd';
import ArrayCopy from '../ArrayCopy'
import ArrayCloud from '../ArrayCloud'

const ArrayAccordion = ({children, render, items = [], ...props}) => {
    return <Collapse size="small" accordion {...props} >
        {children.map((element, index) => {
            if (!element)
                return null
            const {copyItems = [], cloudUrl, ...itemProps} = items[index]
            const extra = <Space>
                <ArrayCloud render={render} cloudUrl={cloudUrl}/>
                <ArrayCopy render={render} copyItems={copyItems}/>
            </Space>
            return <Collapse.Panel key={index} extra={extra} {...itemProps}>
                {element}
            </Collapse.Panel>
        })}
    </Collapse>
};
export default ArrayAccordion;