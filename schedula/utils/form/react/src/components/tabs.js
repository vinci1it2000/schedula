import React, {Suspense, useState} from "react";

const Box = React.lazy(() => import('@mui/material/Box'));
const Tab = React.lazy(() => import('@mui/material/Tab'));
const Tabs = React.lazy(() => import('@mui/material/Tabs'));


function TabPanel(props) {
    const {children, value, index, ...other} = props;

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`tabpanel-${index}`}
            aria-labelledby={`tab-${index}`}
            style={{display: "contents"}}
            {...other}
        >
            {value === index &&
            <Box sx={{p: 3, width: "100%"}}>{children} </Box>}
        </div>
    );
}

function a11yProps(index) {
    return {
        id: `tab-${index}`,
        'aria-controls': `tabpanel-${index}`,
    };
}

export default function _tabs(props) {
    const [value, setValue] = useState(0);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    return (<Suspense>
        <Tabs
            value={value}
            onChange={handleChange}
            sx={{borderRight: 1, borderColor: 'divider'}}{...props}
        >
            {props.children.map((element, index) => (
                <Tab key={index}
                     label={element.props.schema.title || `tab ${index}`} {...a11yProps(index)} />
            ))}
        </Tabs>
        {props.children.map((element, index) => (
            <TabPanel key={index} value={value} index={index}>
                {element}
            </TabPanel>
        ))}
    </Suspense>)
}
